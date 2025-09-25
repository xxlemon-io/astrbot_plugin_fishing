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

    async def exchange_status(self, event: AstrMessageEvent):
        """查看交易所当前状态"""
        user_id = self._get_effective_user_id(event)
        user = self.user_repo.get_by_id(user_id)

        if not user or not user.exchange_account_status:
            yield event.plain_result("您尚未开通交易所账户，请使用【交易所开户】命令开户。")
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
        msg += "💡 使用【交易所购入 商品名称 数量】购买\n"
        msg += "💡 使用【交易所卖出 商品名称】出售所有该商品\n"
        msg += "💡 使用【交易所卖出 库存ID 数量】出售指定数量\n"
        msg += "💡 库存ID格式：C开头+Base36编码（如C1A、C2B）\n"
        msg += "💡 可用商品：鱼干、鱼卵、鱼油\n"
        msg += "💡 大宗商品可上架市场：/上架 C1A 1000\n"
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
        if len(args) < 3:
            yield event.plain_result("❌ 命令格式错误，请使用：交易所购入 [商品名称] [数量]\n💡 可用商品：鱼干、鱼卵、鱼油")
            return
            
        # 支持商品名称包含空格的情况
        commodity_name = args[1]
        if len(args) > 3:
            # 如果商品名称包含空格，需要重新组合
            commodity_name = " ".join(args[1:-1])
            quantity_str = args[-1]
        else:
            quantity_str = args[2]
            
        try:
            quantity = int(quantity_str)
        except ValueError:
            yield event.plain_result("❌ 数量必须是有效的数字")
            return

        result = self.exchange_service.purchase_commodity(user_id, commodity_name, quantity)
        if result["success"]:
            yield event.plain_result(f"✅ {result['message']}")
        else:
            yield event.plain_result(f"❌ {result['message']}")

    async def sell_commodity(self, event: AstrMessageEvent):
        """出售大宗商品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split()
        
        if len(args) == 2:
            # 格式：交易所卖出 鱼油（卖出所有该商品）
            commodity_name = args[1]
            result = self.exchange_service.sell_commodity_by_name(user_id, commodity_name)
            if result["success"]:
                yield event.plain_result(f"✅ {result['message']}")
            else:
                yield event.plain_result(f"❌ {result['message']}")
        elif len(args) == 3:
            # 格式：交易所卖出 [库存ID] [数量]
            inventory_id_str = args[1]
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
                quantity = int(args[2])
            except ValueError:
                yield event.plain_result("❌ 数量必须是有效的数字")
                return

            result = self.exchange_service.sell_commodity(user_id, instance_id, quantity)
            if result["success"]:
                yield event.plain_result(f"✅ {result['message']}")
            else:
                yield event.plain_result(f"❌ {result['message']}")
        else:
            yield event.plain_result("❌ 命令格式错误，请使用：\n• 交易所卖出 商品名称（卖出所有该商品）\n• 交易所卖出 库存ID 数量（卖出指定数量）")
