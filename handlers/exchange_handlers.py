from astrbot.api.event import AstrMessageEvent
from typing import Optional
from datetime import datetime

class ExchangeHandlers:
    def __init__(self, plugin):
        self.plugin = plugin
        self.exchange_service = plugin.exchange_service
        self.user_repo = plugin.user_repo

    def _get_effective_user_id(self, event: AstrMessageEvent) -> str:
        return self.plugin._get_effective_user_id(event)
    
    def _to_base36(self, n: int) -> str:
        """将数字转换为Base36字符串"""
        if n == 0:
            return "0"
        out = []
        while n > 0:
            n, remainder = divmod(n, 36)
            out.append("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[remainder])
        return "".join(reversed(out))

    def _get_commodity_display_code(self, instance_id: int) -> str:
        """生成大宗商品的显示ID"""
        return f"C{self._to_base36(instance_id)}"
    
    def _from_base36(self, s: str) -> int:
        """将base36字符串转换为数字"""
        return int(s, 36)
    
    def _parse_commodity_display_code(self, code: str) -> Optional[int]:
        """解析大宗商品的显示ID，返回instance_id"""
        code = code.strip().upper()
        if code.startswith('C') and len(code) > 1:
            try:
                return self._from_base36(code[1:])
            except ValueError:
                return None
        return None

    async def exchange_main(self, event: AstrMessageEvent):
        """交易所主命令，根据参数分发到不同功能"""
        args = event.message_str.split()
        
        if len(args) == 1:
            # 无参数，显示交易所状态
            async for r in self.exchange_status(event):
                yield r
        elif len(args) >= 2:
            subcommand = args[1]
            
            if subcommand in ["开户"]:
                async for r in self.open_exchange_account(event):
                    yield r
            elif subcommand in ["库存", "持仓"]:
                async for r in self.view_inventory(event):
                    yield r
            elif subcommand in ["购入", "购买"]:
                async for r in self.buy_commodity(event):
                    yield r
            elif subcommand in ["卖出", "出售"]:
                async for r in self.sell_commodity(event):
                    yield r
            elif subcommand in ["清仓"]:
                async for r in self.clear_inventory(event):
                    yield r
            elif subcommand in ["帮助"]:
                async for r in self.exchange_help(event):
                    yield r
            else:
                yield event.plain_result("❌ 未知的子命令，请使用：\n• 交易所 - 查看市场行情\n• 交易所 开户 - 开通账户\n• 交易所 库存 - 查看库存\n• 交易所 购入 商品名称 数量 - 购买\n• 交易所 卖出 商品名称 - 卖出所有\n• 交易所 卖出 库存ID 数量 - 卖出指定数量\n• 交易所 帮助 - 查看所有玩法\n• /清仓 - 清空所有库存")

    async def exchange_status(self, event: AstrMessageEvent):
        """查看交易所当前状态"""
        user_id = self._get_effective_user_id(event)
        user = self.user_repo.get_by_id(user_id)
        
        if not user or not user.exchange_account_status:
            yield event.plain_result("您尚未开通交易所账户，请使用【交易所 开户】命令开户。")
            return

        result = self.exchange_service.get_market_status()
        if not result["success"]:
            yield event.plain_result(f"❌ 查询失败: {result.get('message', '未知错误')}")
            return
        
        prices = result["prices"]
        commodities = result["commodities"]
        
        msg = "【📈 交易所实时行情】\n"
        msg += "═" * 25 + "\n"
        for comm_id, price in prices.items():
            commodity = commodities.get(comm_id)
            if commodity:
                # 根据商品类型添加腐败时间说明
                if comm_id == 'dried_fish':
                    corruption_info = "保质期: 3天"
                elif comm_id == 'fish_roe':
                    corruption_info = "保质期: 2天"
                elif comm_id == 'fish_oil':
                    corruption_info = "保质期: 1-3天随机"
                else:
                    corruption_info = "保质期: 未知"
                
                msg += f"商品: {commodity.name}\n"
                msg += f"价格: {price} 金币\n"
                msg += f"腐败时间: {corruption_info}\n"
                msg += "─" * 20 + "\n"
        msg += "═" * 25 + "\n"

        # 显示持仓容量
        capacity = self.plugin.exchange_service.config.get("capacity", 1000)
        user_commodities = self.plugin.exchange_service.exchange_repo.get_user_commodities(user_id)
        current_total_quantity = sum(item.quantity for item in user_commodities)
        msg += f"📦 当前持仓: {current_total_quantity} / {capacity}\n"

        msg += "💡 使用【交易所 购入 商品名称 数量】购买\n"
        msg += "💡 使用【交易所 卖出 商品名称】出售所有该商品\n"
        msg += "💡 快速清仓：/清仓 或 /清仓 商品名称\n"
        msg += "💡 快速查看持仓：/持仓\n"
        msg += "💡 大宗商品可上架二级市场：/上架 C1A 1000\n"
        msg += "💡 查看所有玩法：/交易所 帮助\n"
        msg += "⚠️ 注意：商品会腐败，请及时交易！"
        yield event.plain_result(msg)

    async def open_exchange_account(self, event: AstrMessageEvent):
        """开通交易所账户"""
        user_id = self._get_effective_user_id(event)
        result = self.exchange_service.open_account(user_id)
        if result["success"]:
            yield event.plain_result(f"✅ {result['message']}")
        else:
            yield event.plain_result(f"❌ {result['message']}")

    async def view_inventory(self, event: AstrMessageEvent):
        """查看大宗商品库存"""
        user_id = self._get_effective_user_id(event)
        result = self.exchange_service.get_user_inventory(user_id)

        if not result["success"]:
            yield event.plain_result(f"❌ {result.get('message', '查询失败')}")
            return
            
        inventory = result["inventory"]
        commodities = result["commodities"]
        
        if not inventory:
            yield event.plain_result("您的交易所库存为空。")
            return

        msg = "【📦 我的交易所库存】\n"
        msg += "═" * 25 + "\n"
        for item in inventory:
            commodity = commodities.get(item.commodity_id)
            if commodity:
                time_left = item.expires_at - datetime.now()
                hours, remainder = divmod(time_left.total_seconds(), 3600)
                minutes, _ = divmod(remainder, 60)
                
                # 生成显示ID
                display_id = self._get_commodity_display_code(item.instance_id)
                
                # 根据剩余时间添加不同的警告级别
                if time_left.total_seconds() <= 0:
                    # 已腐败
                    msg += f"库存ID: {display_id}\n"
                    msg += f"商品: {commodity.name} ⚠️ 已腐败\n"
                    msg += f"数量: {item.quantity}\n"
                    msg += f"买入价: {item.purchase_price} 金币\n"
                    msg += f"状态: 💀 腐败中，价值归零\n"
                elif time_left.total_seconds() <= 3600:  # 1小时内
                    # 紧急警告
                    msg += f"库存ID: {display_id}\n"
                    msg += f"商品: {commodity.name} 🚨 即将腐败\n"
                    msg += f"数量: {item.quantity}\n"
                    msg += f"买入价: {item.purchase_price} 金币\n"
                    msg += f"腐败倒计时: ⏰ {int(minutes)}分钟\n"
                elif time_left.total_seconds() <= 86400:  # 24小时内
                    # 警告
                    msg += f"库存ID: {display_id}\n"
                    msg += f"商品: {commodity.name} ⚠️ 注意保质期\n"
                    msg += f"数量: {item.quantity}\n"
                    msg += f"买入价: {item.purchase_price} 金币\n"
                    msg += f"腐败倒计时: ⏳ {int(hours)}小时 {int(minutes)}分钟\n"
                else:
                    # 正常
                    days = int(hours // 24)
                    remaining_hours = int(hours % 24)
                    msg += f"库存ID: {display_id}\n"
                    msg += f"商品: {commodity.name}\n"
                    msg += f"数量: {item.quantity}\n"
                    msg += f"买入价: {item.purchase_price} 金币\n"
                    msg += f"腐败倒计时: ⏰ {days}天 {remaining_hours}小时\n"
                
                msg += "─" * 20 + "\n"
        msg += "═" * 25 + "\n"
        yield event.plain_result(msg)

    async def buy_commodity(self, event: AstrMessageEvent):
        """购买大宗商品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split()
        if len(args) < 4:
            yield event.plain_result("❌ 命令格式错误，请使用：交易所 购入 [商品名称] [数量]\n💡 可用商品：鱼干、鱼卵、鱼油")
            return
            
        # 支持商品名称包含空格的情况
        commodity_name = args[2]
        if len(args) > 3:
            # 如果商品名称包含空格，需要重新组合
            commodity_name = " ".join(args[2:-1])
            quantity = int(args[-1])
        else:
            quantity = int(args[3])

        result = self.exchange_service.purchase_commodity(user_id, commodity_name, quantity)
        if result["success"]:
            yield event.plain_result(f"✅ {result['message']}")
        else:
            yield event.plain_result(f"❌ {result['message']}")

    async def sell_commodity(self, event: AstrMessageEvent):
        """出售大宗商品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split()
        
        if len(args) == 3:
            # 格式：交易所 卖出 鱼油（卖出所有该商品）
            commodity_name = args[2]
            result = self.exchange_service.sell_commodity_by_name(user_id, commodity_name)
            if result["success"]:
                yield event.plain_result(f"✅ {result['message']}")
            else:
                yield event.plain_result(f"❌ {result['message']}")
        elif len(args) == 4:
            # 格式：交易所 卖出 [库存ID] [数量]
            inventory_id_str = args[2]
            instance_id = None
            
            # 先尝试解析Base36格式（C开头）
            if inventory_id_str.upper().startswith('C'):
                instance_id = self._parse_commodity_display_code(inventory_id_str)
                if instance_id is None:
                    yield event.plain_result("❌ 无效的库存ID格式")
                    return
            else:
                # 尝试解析数字格式（向后兼容）
                try:
                    instance_id = int(inventory_id_str)
                except ValueError:
                    yield event.plain_result("❌ 库存ID格式错误，请使用C开头的ID或数字ID")
                    return
            
            try:
                quantity = int(args[3])
            except ValueError:
                yield event.plain_result("❌ 数量必须是有效的数字")
                return

            result = self.exchange_service.sell_commodity(user_id, instance_id, quantity)
            if result["success"]:
                yield event.plain_result(f"✅ {result['message']}")
            else:
                yield event.plain_result(f"❌ {result['message']}")
        else:
            yield event.plain_result("❌ 命令格式错误，请使用：\n• 交易所 卖出 商品名称（卖出所有该商品）\n• 交易所 卖出 库存ID 数量（卖出指定数量）")

    async def clear_inventory(self, event: AstrMessageEvent):
        """清仓功能 - 快速卖出某一种类或全部商品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split()
        
        if len(args) == 1:
            # 格式：/清仓（清空所有库存）
            result = self.exchange_service.clear_all_inventory(user_id)
            if result["success"]:
                yield event.plain_result(f"✅ {result['message']}")
            else:
                yield event.plain_result(f"❌ {result['message']}")
        elif len(args) == 2:
            target = args[1].lower()
            
            if target == "all":
                # 清空所有库存
                result = self.exchange_service.clear_all_inventory(user_id)
                if result["success"]:
                    yield event.plain_result(f"✅ {result['message']}")
                else:
                    yield event.plain_result(f"❌ {result['message']}")
            else:
                # 清空指定商品
                commodity_name = args[1]
                result = self.exchange_service.sell_commodity_by_name(user_id, commodity_name)
                if result["success"]:
                    yield event.plain_result(f"✅ {result['message']}")
                else:
                    yield event.plain_result(f"❌ {result['message']}")
        else:
            yield event.plain_result("❌ 命令格式错误，请使用：\n• /清仓 - 清空所有库存\n• /清仓 商品名称 - 清空指定商品\n• /清仓 all - 清空所有库存")

    async def exchange_help(self, event: AstrMessageEvent):
        """交易所帮助信息"""
        message = """【📈 交易所系统帮助】

🎯 系统介绍：
交易所是一个大宗商品交易平台，支持鱼干、鱼卵、鱼油三种商品交易。
所有商品都有腐败机制，必须在有效期内交易，否则价值归零。

💰 开户费用：100,000 金币

📋 可用命令：
• /交易所 - 查看当前市场行情和价格
• /交易所 开户 - 开通交易所账户
• /交易所 购入 商品名称 数量 - 购买大宗商品
• /交易所 卖出 商品名称 - 卖出所有该商品
• /交易所 卖出 库存ID 数量 - 卖出指定数量
• /交易所 帮助 - 显示此帮助信息
• /持仓 - 快速查看大宗商品库存（独立命令）
• /清仓 - 清空所有库存（独立命令）
• /清仓 商品名称 - 清空指定商品（独立命令）

🛒 商品信息：
• 鱼干：价格稳健，保质期3天
• 鱼卵：高风险，保质期2天  
• 鱼油：投机品，价格波动大，保质期1-3天（每日固定）

💡 交易技巧：
• 鱼干适合稳健型玩家，风险低但收益有限
• 鱼卵适合激进型玩家，高风险高收益
• 鱼油适合赌徒型玩家，既要赌价格还要赌腐败时间
• 大宗商品可上架玩家市场：/上架 C1A 1000

⚠️ 重要提醒：
• 商品会腐败，请及时交易！
• 腐败后价值归零，无法挽回
• 购买新商品时自动清理腐败商品
• 交易所总容量为1000，所有商品共享
• 库存ID格式：C开头+Base36编码（如C1A、C2B）
• 每日9点、15点、21点更新价格，鱼油腐败时间每日固定

🔗 相关系统：
• 玩家市场：/市场 - 查看玩家交易市场
• 上架商品：/上架 C1A 1000 - 将大宗商品上架到玩家市场"""
        
        yield event.plain_result(message)