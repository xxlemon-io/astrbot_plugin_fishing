from astrbot.api.event import AstrMessageEvent
from typing import Optional, Dict, Any
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
    
    def _calculate_inventory_profit_loss(self, inventory: Dict[str, Any], current_prices: Dict[str, int]) -> Dict[str, Any]:
        """计算库存盈亏分析 - 统一的数据流方法"""
        try:
            total_cost = 0
            total_current_value = 0
            
            for commodity_id, commodity_data in inventory.items():
                total_cost += commodity_data.get("total_cost", 0)
                current_price = current_prices.get(commodity_id, 0)
                total_current_value += current_price * commodity_data.get("total_quantity", 0)
            
            profit_loss = total_current_value - total_cost
            profit_rate = (profit_loss / total_cost * 100) if total_cost > 0 else 0
            
            return {
                "total_cost": total_cost,
                "total_current_value": total_current_value,
                "profit_loss": profit_loss,
                "profit_rate": profit_rate,
                "is_profit": profit_loss > 0
            }
        except Exception as e:
            from astrbot.api import logger
            logger.error(f"计算库存盈亏分析失败: {e}")
            return {
                "total_cost": 0,
                "total_current_value": 0,
                "profit_loss": 0,
                "profit_rate": 0,
                "is_profit": False
            }
    
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
            command = args[1].lower()
            if command in ["开户", "account"]:
                async for r in self.open_exchange_account(event):
                    yield r
            elif command in ["买入", "buy", "purchase"]:
                async for r in self.buy_commodity(event):
                    yield r
            elif command in ["卖出", "sell"]:
                async for r in self.sell_commodity(event):
                    yield r
            elif command in ["帮助", "help"]:
                yield event.plain_result(self._get_exchange_help())
            else:
                yield event.plain_result("❌ 未知命令。使用【交易所 帮助】查看可用命令。")

    def _get_exchange_help(self) -> str:
        """获取交易所帮助信息"""
        return """【📈 交易所帮助】
        - 交易所: 查看市场状态
        - 交易所 开户: 开通账户
        - 交易所 买入 [商品] [数量]
        - 交易所 卖出 [商品]
        - 交易所 卖出 [库存ID] [数量]
        - /持仓: 查看我的库存
        - /清仓: 卖出所有库存
        - /清仓 [商品]: 卖出指定商品
        """

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
        
        msg = "【📈 交易所行情】\n"
        msg += f"更新时间: {result.get('date', 'N/A')}\n"
        msg += "═" * 30 + "\n"
        
        for comm_id, price in prices.items():
            commodity = commodities.get(comm_id)
            if commodity:
                msg += f"商品: {commodity['name']}\n"
                msg += f"价格: {price:,} 金币\n"
                msg += "─" * 20 + "\n"
        
        # 显示持仓容量和盈亏分析
        capacity = self.plugin.exchange_service.config.get("capacity", 1000)
        
        inventory_result = self.plugin.exchange_service.get_user_inventory(user_id)
        if inventory_result["success"]:
            inventory = inventory_result["inventory"]
            current_total_quantity = sum(data.get("total_quantity", 0) for data in inventory.values())
            msg += f"📦 当前持仓: {current_total_quantity} / {capacity}\n"
            
            if inventory:
                analysis = self._calculate_inventory_profit_loss(inventory, prices)
                profit_status = "📈盈利" if analysis["is_profit"] else "📉亏损" if analysis["profit_loss"] < 0 else "➖持平"
                msg += f"📊 持仓盈亏: {analysis['profit_loss']:+} 金币 ({analysis['profit_rate']:+.1f}%)\n"
        else:
            msg += f"📦 当前持仓: 无法获取 / {capacity}\n"

        msg += "═" * 30 + "\n"
        msg += "💡 使用【交易所 帮助】查看更多命令。"
        
        yield event.plain_result(msg)

    async def open_exchange_account(self, event: AstrMessageEvent):
        """开通交易所账户"""
        user_id = self._get_effective_user_id(event)
        result = self.exchange_service.open_exchange_account(user_id)
        yield event.plain_result(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")

    async def view_inventory(self, event: AstrMessageEvent):
        """查看大宗商品库存"""
        try:
            from astrbot.api import logger
            user_id = self._get_effective_user_id(event)
            
            result = self.exchange_service.get_user_inventory(user_id)
            if not result["success"]:
                yield event.plain_result(f"❌ {result.get('message', '查询失败')}")
                return
                
            inventory = result["inventory"]
            if not inventory:
                yield event.plain_result("您的交易所库存为空。")
                return

            market_status = self.exchange_service.get_market_status()
            current_prices = market_status.get("prices", {})
            
            analysis = self._calculate_inventory_profit_loss(inventory, current_prices)

            msg = "【📦 我的交易所库存】\n"
            msg += "═" * 30 + "\n"
            
            profit_status = "📈盈利" if analysis["is_profit"] else "📉亏损" if analysis["profit_loss"] < 0 else "➖持平"
            msg += f"📊 总体盈亏：{analysis['profit_loss']:+} 金币 {profit_status}\n"
            msg += f"💰 总成本：{analysis['total_cost']:,} 金币\n"
            msg += f"💎 当前价值：{analysis['total_current_value']:,} 金币\n"
            msg += f"📈 盈利率：{analysis['profit_rate']:+.1f}%\n"
            msg += "─" * 30 + "\n"
            
            for commodity_id, commodity_data in inventory.items():
                try:
                    commodity_name = commodity_data.get("name", "未知商品")
                    total_quantity = commodity_data.get("total_quantity", 0)
                    
                    current_price = current_prices.get(commodity_id, 0)
                    current_value = current_price * total_quantity
                    profit_loss = current_value - commodity_data.get("total_cost", 0)
                    profit_status = "📈" if profit_loss > 0 else "📉" if profit_loss < 0 else "➖"
                    msg += f"{commodity_name} ({total_quantity}个) - 盈亏: {profit_loss:+}金币 {profit_status}\n"

                    for item in commodity_data.get("items", []):
                        if not isinstance(item, dict): continue

                        expires_at = item.get("expires_at")
                        instance_id = item.get("instance_id")
                        quantity = item.get("quantity", 0)

                        if expires_at and isinstance(expires_at, datetime) and instance_id is not None:
                            time_left = expires_at - datetime.now()
                            display_id = self._get_commodity_display_code(instance_id)

                            if time_left.total_seconds() <= 0:
                                time_str = "💀 已腐败"
                            elif time_left.total_seconds() < 86400:
                                hours = int(time_left.total_seconds() // 3600)
                                time_str = f"⚠️剩{hours}小时"
                            else:
                                days = int(time_left.total_seconds() // 86400)
                                time_str = f"✅剩{days}天"
                            
                            msg += f"  └─ {display_id}: {quantity}个 ({time_str})\n"
                    
                except Exception as e:
                    logger.error(f"处理库存项失败: {e}")
                    continue
            
            msg += "═" * 30 + "\n"
            
            capacity = self.exchange_service.config.get("capacity", 1000)
            current_total_quantity = sum(data.get("total_quantity", 0) for data in inventory.values())
            msg += f"📦 当前持仓: {current_total_quantity} / {capacity}\n"

            yield event.plain_result(msg)

        except Exception as e:
            from astrbot.api import logger
            logger.error(f"持仓命令执行失败: {e}")
            yield event.plain_result(f"❌ 持仓命令执行失败: {e}")

    async def buy_commodity(self, event: AstrMessageEvent):
        """购买大宗商品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split()

        if len(args) != 4:
            yield event.plain_result("❌ 命令格式错误，请使用：交易所 买入 [商品名称] [数量]")
            return
            
        commodity_name = args[2]
        try:
            quantity = int(args[3])
            if quantity <= 0:
                yield event.plain_result("❌ 数量必须是正整数")
                return
        except ValueError:
            yield event.plain_result("❌ 数量必须是有效的数字")
            return

        market_status = self.exchange_service.get_market_status()
        if not market_status["success"]:
            yield event.plain_result(f"❌ 获取价格失败: {market_status.get('message', '未知错误')}")
            return
        
        commodity_id = None
        for cid, info in market_status["commodities"].items():
            if info["name"] == commodity_name:
                commodity_id = cid
                break
        
        if not commodity_id:
            yield event.plain_result(f"❌ 找不到商品: {commodity_name}")
            return
        
        current_price = market_status["prices"].get(commodity_id, 0)
        if current_price <= 0:
            yield event.plain_result(f"❌ 商品 {commodity_name} 价格异常")
            return
        
        result = self.exchange_service.purchase_commodity(user_id, commodity_id, quantity, current_price)
        yield event.plain_result(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")

    async def sell_commodity(self, event: AstrMessageEvent):
        """卖出大宗商品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split()

        market_status = self.exchange_service.get_market_status()
        if not market_status["success"]:
            yield event.plain_result(f"❌ 获取价格失败: {market_status.get('message', '未知错误')}")
            return
        
        if len(args) == 3:
            commodity_name = args[2]
            
            commodity_id = None
            for cid, info in market_status["commodities"].items():
                if info["name"] == commodity_name:
                    commodity_id = cid
                    break
            
            if not commodity_id:
                yield event.plain_result(f"❌ 找不到商品: {commodity_name}")
                return
            
            current_price = market_status["prices"].get(commodity_id, 0)
            if current_price <= 0:
                yield event.plain_result(f"❌ 商品 {commodity_name} 价格异常")
                return
            
            inventory = self.exchange_service.get_user_commodities(user_id)
            commodity_items = [item for item in inventory if item.commodity_id == commodity_id]
            
            if not commodity_items:
                yield event.plain_result(f"❌ 您没有 {commodity_name}")
                return
            
            total_quantity = sum(item.quantity for item in commodity_items)
            
            result = self.exchange_service.sell_commodity(user_id, commodity_id, total_quantity, current_price)
            yield event.plain_result(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")

        elif len(args) == 4:
            inventory_id_str = args[2]
            
            instance_id = self._parse_commodity_display_code(inventory_id_str)
            if instance_id is None:
                yield event.plain_result("❌ 库存ID格式错误，请使用C开头的ID")
                return
            
            try:
                quantity = int(args[3])
                if quantity <= 0:
                    yield event.plain_result("❌ 数量必须是正整数")
                    return
            except ValueError:
                yield event.plain_result("❌ 数量必须是有效的数字")
                return

            inventory = self.exchange_service.get_user_commodities(user_id)
            commodity_item = next((item for item in inventory if item.instance_id == instance_id), None)
            
            if not commodity_item:
                yield event.plain_result("❌ 找不到指定的库存项目")
                return
            
            current_price = market_status["prices"].get(commodity_item.commodity_id, 0)
            if current_price <= 0:
                yield event.plain_result(f"❌ 商品价格异常")
                return
            
            result = self.exchange_service.sell_commodity_by_instance(user_id, instance_id, quantity, current_price)
            yield event.plain_result(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")
        else:
            yield event.plain_result("❌ 命令格式错误，请使用帮助查看。")

    async def clear_inventory(self, event: AstrMessageEvent):
        """清仓功能"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split()
        
        if len(args) == 1 or (len(args) == 2 and args[1].lower() == "all"):
            result = self.exchange_service.clear_all_inventory(user_id)
            yield event.plain_result(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")
        elif len(args) == 2:
            commodity_name = args[1]
            
            market_status = self.exchange_service.get_market_status()
            if not market_status["success"]:
                yield event.plain_result(f"❌ 获取价格失败: {market_status.get('message', '未知错误')}")
                return
                
            commodity_id = None
            for cid, info in market_status["commodities"].items():
                if info["name"] == commodity_name:
                    commodity_id = cid
                    break
            
            if not commodity_id:
                yield event.plain_result(f"❌ 找不到商品: {commodity_name}")
                return
            
            result = self.exchange_service.clear_commodity_inventory(user_id, commodity_id)
            yield event.plain_result(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")
        else:
            yield event.plain_result("❌ 命令格式错误，请使用：/清仓 或 /清仓 [商品名称]")