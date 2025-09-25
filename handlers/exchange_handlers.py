from astrbot.api.event import filter, AstrMessageEvent
from datetime import datetime

class ExchangeHandlers:
    def __init__(self, plugin):
        self.plugin = plugin
        self.exchange_service = plugin.exchange_service
        self.user_repo = plugin.user_repo

    def _get_effective_user_id(self, event: AstrMessageEvent) -> str:
        return str(event.get_user_id())

    @filter(commands=["交易所", "exchange"])
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
        msg += "💡 使用【交易所卖出 库存ID 数量】出售\n"
        msg += "💡 可用商品：鱼干、鱼卵、鱼油\n"
        msg += "⚠️ 注意：商品会腐败，请及时交易！"
        yield event.plain_result(msg)

    @filter(commands=["交易所开户", "open_exchange_account"])
    async def open_exchange_account(self, event: AstrMessageEvent):
        """开通交易所账户"""
        user_id = self._get_effective_user_id(event)
        result = self.exchange_service.open_account(user_id)
        if result["success"]:
            yield event.plain_result(f"✅ {result['message']}")
        else:
            yield event.plain_result(f"❌ {result['message']}")

    @filter(commands=["查看库存", "inventory", "持仓"])
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
                
                # 根据剩余时间添加不同的警告级别
                if time_left.total_seconds() <= 0:
                    # 已腐败
                    msg += f"库存ID: {item.instance_id}\n"
                    msg += f"商品: {commodity.name} ⚠️ 已腐败\n"
                    msg += f"数量: {item.quantity}\n"
                    msg += f"买入价: {item.purchase_price} 金币\n"
                    msg += f"状态: 💀 腐败中，价值归零\n"
                elif time_left.total_seconds() <= 3600:  # 1小时内
                    # 紧急警告
                    msg += f"库存ID: {item.instance_id}\n"
                    msg += f"商品: {commodity.name} 🚨 即将腐败\n"
                    msg += f"数量: {item.quantity}\n"
                    msg += f"买入价: {item.purchase_price} 金币\n"
                    msg += f"腐败倒计时: ⏰ {int(minutes)}分钟\n"
                elif time_left.total_seconds() <= 86400:  # 24小时内
                    # 警告
                    msg += f"库存ID: {item.instance_id}\n"
                    msg += f"商品: {commodity.name} ⚠️ 注意保质期\n"
                    msg += f"数量: {item.quantity}\n"
                    msg += f"买入价: {item.purchase_price} 金币\n"
                    msg += f"腐败倒计时: ⏳ {int(hours)}小时 {int(minutes)}分钟\n"
                else:
                    # 正常
                    days = int(hours // 24)
                    remaining_hours = int(hours % 24)
                    msg += f"库存ID: {item.instance_id}\n"
                    msg += f"商品: {commodity.name}\n"
                    msg += f"数量: {item.quantity}\n"
                    msg += f"买入价: {item.purchase_price} 金币\n"
                    msg += f"腐败倒计时: ⏰ {days}天 {remaining_hours}小时\n"
                
                msg += "─" * 20 + "\n"
        msg += "═" * 25 + "\n"
        yield event.plain_result(msg)

    @filter(commands=["交易所购入", "exchange_buy"])
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

    @filter(commands=["交易所卖出", "exchange_sell"])
    async def sell_commodity(self, event: AstrMessageEvent):
        """出售大宗商品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split()
        if len(args) != 3:
            yield event.plain_result("❌ 命令格式错误，请使用：交易所卖出 [库存ID] [数量]")
            return
            
        try:
            instance_id = int(args[1])
            quantity = int(args[2])
        except ValueError:
            yield event.plain_result("❌ 库存ID和数量必须是有效的数字")
            return

        result = self.exchange_service.sell_commodity(user_id, instance_id, quantity)
        if result["success"]:
            yield event.plain_result(f"✅ {result['message']}")
        else:
            yield event.plain_result(f"❌ {result['message']}")
