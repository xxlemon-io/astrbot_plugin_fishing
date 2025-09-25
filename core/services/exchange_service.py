import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from astrbot.api import logger
from ..domain.models import User, Exchange, UserCommodity, Commodity
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractExchangeRepository,
)

class ExchangeService:
    def __init__(
        self,
        user_repo: AbstractUserRepository,
        exchange_repo: AbstractExchangeRepository,
        config: Dict[str, Any],
        log_repo=None,
    ):
        self.user_repo = user_repo
        self.exchange_repo = exchange_repo
        self.config = config.get("exchange", {})
        self.log_repo = log_repo
        
        # 安全地获取商品数据
        try:
            commodities_list = self.exchange_repo.get_all_commodities()
            self.commodities = {c.commodity_id: c for c in commodities_list}
            # 创建中文名称到商品ID的映射
            self.name_to_id = {c.name: c.commodity_id for c in self.commodities.values()}
        except Exception as e:
            # 如果获取商品数据失败，使用空字典
            logger.warning(f"警告：无法获取商品数据: {e}")
            self.commodities = {}
            self.name_to_id = {}
        
        self._price_update_task = None

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

    def _resolve_commodity_id(self, commodity_input: str) -> Optional[str]:
        """解析商品输入，支持中文名称和英文ID"""
        # 首先尝试直接匹配商品ID
        if commodity_input in self.commodities:
            return commodity_input
        
        # 然后尝试通过中文名称查找
        if commodity_input in self.name_to_id:
            return self.name_to_id[commodity_input]
        
        # 支持部分匹配
        for name, commodity_id in self.name_to_id.items():
            if commodity_input in name or name in commodity_input:
                return commodity_id
        
        return None

    def open_account(self, user_id: str) -> Dict[str, Any]:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        if user.exchange_account_status:
            return {"success": False, "message": "您已经开通了交易所账户"}

        account_fee = self.config.get("account_fee", 100000)
        if not user.can_afford(account_fee):
            return {"success": False, "message": f"金币不足，开户需要 {account_fee} 金币"}

        user.coins -= account_fee
        user.exchange_account_status = True
        self.user_repo.update(user)

        return {"success": True, "message": f"交易所账户开通成功，花费 {account_fee} 金币"}

    def get_market_status(self) -> Dict[str, Any]:
        today_str = datetime.now().strftime("%Y-%m-%d")
        prices = self.exchange_repo.get_prices_for_date(today_str)
        
        if not prices:
            self.update_daily_prices()
            prices = self.exchange_repo.get_prices_for_date(today_str)

        price_data = {p.commodity_id: p.price for p in prices}
        return {"success": True, "prices": price_data, "commodities": self.commodities}

    def update_daily_prices(self) -> None:
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 获取今日已有价格作为基础
        today_prices = self.exchange_repo.get_prices_for_date(today_str)
        if today_prices:
            # 如果今日已有价格，使用今日价格作为基础进行更新
            last_prices = {p.commodity_id: p.price for p in today_prices}
            logger.info(f"基于今日已有价格更新：{last_prices}")
        else:
            # 如果今日没有价格，使用昨日价格作为基础
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            last_prices = {p.commodity_id: p.price for p in self.exchange_repo.get_prices_for_date(yesterday_str)}
            logger.info(f"基于昨日价格更新：{last_prices}")

        # 如果没有商品数据，跳过价格更新
        if not self.commodities:
            return

        # 先删除今日的旧价格（如果存在）
        if today_prices:
            self.exchange_repo.delete_prices_for_date(today_str)
            logger.info(f"已删除今日旧价格，准备更新")
        
        # 生成新的价格
        new_prices = {}
        for commodity_id, commodity in self.commodities.items():
            last_price = last_prices.get(commodity_id, self.config.get("initial_prices", {}).get(commodity_id, 100))
            new_price = self._calculate_new_price(commodity_id, last_price)
            new_prices[commodity_id] = new_price
            self.exchange_repo.add_exchange_price(Exchange(date=today_str, commodity_id=commodity_id, price=new_price))
        
        logger.info(f"价格更新完成，新价格：{new_prices}")

    def _calculate_new_price(self, commodity_id: str, last_price: int) -> int:
        volatility = self.config.get("volatility", {})
        if commodity_id == 'dried_fish':
            change_percent = random.uniform(-volatility.get('dried_fish', 0.1), volatility.get('dried_fish', 0.1))
        elif commodity_id == 'fish_roe':
            change_percent = random.uniform(-volatility.get('fish_roe', 0.5), volatility.get('fish_roe', 0.5))
        elif commodity_id == 'fish_oil':
            change_percent = random.uniform(-volatility.get('fish_oil', 0.25), volatility.get('fish_oil', 0.25))
            if random.random() < self.config.get("event_chance", 0.1):  # 10% chance for an event
                change_percent = random.choice([-2.0, 2.0])
        else:
            change_percent = 0

        new_price = int(last_price * (1 + change_percent))
        return max(1, new_price)  # Price shouldn't be zero or negative

    def get_user_inventory(self, user_id: str) -> Dict[str, Any]:
        user = self.user_repo.get_by_id(user_id)
        if not user or not user.exchange_account_status:
            return {"success": False, "message": "您尚未开通交易所账户或用户不存在"}
        
        inventory = self.exchange_repo.get_user_commodities(user_id)
        return {"success": True, "inventory": inventory, "commodities": self.commodities}

    def purchase_commodity(self, user_id: str, commodity_input: str, quantity: int) -> Dict[str, Any]:
        user = self.user_repo.get_by_id(user_id)
        if not user or not user.exchange_account_status:
            return {"success": False, "message": "您尚未开通交易所账户或用户不存在"}

        if quantity <= 0:
            return {"success": False, "message": "购买数量必须为正数"}
        
        # 解析商品ID
        commodity_id = self._resolve_commodity_id(commodity_input)
        if not commodity_id:
            available_commodities = "、".join(self.name_to_id.keys())
            return {"success": False, "message": f"未找到商品 '{commodity_input}'，可用商品：{available_commodities}"}
        
        market_status = self.get_market_status()
        current_price = market_status["prices"].get(commodity_id)
        if not current_price:
            return {"success": False, "message": "该商品今日无报价"}
            
        total_cost = current_price * quantity
        if not user.can_afford(total_cost):
            return {"success": False, "message": f"金币不足，需要 {total_cost} 金币"}

        # 检查交易所容量（包括交易所库存和市场上架的大宗商品）
        capacity = self.config.get("capacity", 1000) # 从配置读取容量，默认为1000
        current_total_quantity = self._get_user_total_commodity_quantity(user_id)

        if current_total_quantity + quantity > capacity:
            remaining_space = capacity - current_total_quantity
            return {"success": False, "message": f"交易所容量不足！总容量: {capacity}，当前已用: {current_total_quantity}，剩余空间: {remaining_space}"}

        # 腐败机制：用户购入时计算腐败时间
        now = datetime.now()
        if commodity_id == 'dried_fish':
            expires_at = now + timedelta(days=3)
        elif commodity_id == 'fish_roe':
            expires_at = now + timedelta(days=2)
        elif commodity_id == 'fish_oil':
            # 每日固定腐败时间：基于日期计算，确保同一天购买的所有鱼油腐败时间相同
            days = self._get_daily_fish_oil_expiry_days()
            expires_at = now + timedelta(days=days)
        else:
            return {"success": False, "message": "未知商品"}

        # 清理腐败仓库
        self.clear_expired_commodities(user_id)

        # 检查是否有相同商品且相同腐败时间的库存，如果有则叠加
        existing_commodities = self.exchange_repo.get_user_commodities(user_id)
        for existing in existing_commodities:
            if (existing.commodity_id == commodity_id and 
                existing.expires_at == expires_at and 
                existing.purchase_price == current_price):
                # 找到相同商品、相同腐败时间、相同价格的库存，直接叠加数量
                self.exchange_repo.update_user_commodity_quantity(existing.instance_id, existing.quantity + quantity)
                user.coins -= total_cost
                self.user_repo.update(user)
                
                commodity_name = self.commodities[commodity_id].name
                days_until_expiry = (expires_at - now).days
                if commodity_id == 'fish_oil':
                    corruption_warning = f"，{days_until_expiry}天后将腐败（今日固定）"
                else:
                    corruption_warning = f"，{days_until_expiry}天后将腐败"
                
                return {"success": True, "message": f"成功购买 {quantity}份 {commodity_name}，花费 {total_cost} 金币{corruption_warning}（已叠加到现有库存）"}

        # 没有找到可叠加的库存，创建新的商品实例
        user.coins -= total_cost
        self.user_repo.update(user)
        
        new_commodity = UserCommodity(
            instance_id=0,
            user_id=user_id,
            commodity_id=commodity_id,
            quantity=quantity,
            purchase_price=current_price,
            purchased_at=now,
            expires_at=expires_at
        )
        self.exchange_repo.add_user_commodity(new_commodity)

        commodity_name = self.commodities[commodity_id].name
        
        # 根据商品类型添加腐败时间警告
        if commodity_id == 'dried_fish':
            corruption_warning = "，3天后将腐败"
        elif commodity_id == 'fish_roe':
            corruption_warning = "，2天后将腐败"
        elif commodity_id == 'fish_oil':
            # 计算具体的天数
            days_until_expiry = (expires_at - now).days
            corruption_warning = f"，{days_until_expiry}天后将腐败（今日固定）"
        else:
            corruption_warning = "，注意保质期"
        
        return {"success": True, "message": f"成功购买 {quantity}份 {commodity_name}，花费 {total_cost} 金币{corruption_warning}"}

    def sell_commodity(self, user_id: str, instance_id: int, quantity: int) -> Dict[str, Any]:
        user = self.user_repo.get_by_id(user_id)
        if not user or not user.exchange_account_status:
            return {"success": False, "message": "您尚未开通交易所账户或用户不存在"}

        user_commodity = self.exchange_repo.get_user_commodity_by_instance_id(instance_id)
        if not user_commodity or user_commodity.user_id != user_id:
            return {"success": False, "message": "未找到指定的库存商品"}

        if quantity <= 0:
            return {"success": False, "message": "出售数量必须为正数"}
        
        if user_commodity.quantity < quantity:
            return {"success": False, "message": f"数量不足，您只有 {user_commodity.quantity} 份"}
            
        market_status = self.get_market_status()
        current_price = market_status["prices"].get(user_commodity.commodity_id)
        if not current_price:
            return {"success": False, "message": "该商品今日无报价，无法出售"}

        total_earnings = current_price * quantity
        user.coins += total_earnings
        self.user_repo.update(user)

        remaining_quantity = user_commodity.quantity - quantity
        if remaining_quantity > 0:
            self.exchange_repo.update_user_commodity_quantity(instance_id, remaining_quantity)
        else:
            self.exchange_repo.delete_user_commodity(instance_id)

        commodity_name = self.commodities[user_commodity.commodity_id].name
        
        # 检查是否在腐败前及时出售
        time_left = user_commodity.expires_at - datetime.now()
        if time_left.total_seconds() <= 0:
            urgency_msg = "（已腐败，价值归零）"
        elif time_left.total_seconds() <= 3600:  # 1小时内
            urgency_msg = "（及时止损！）"
        elif time_left.total_seconds() <= 86400:  # 24小时内
            urgency_msg = "（即将腐败）"
        else:
            urgency_msg = ""
        
        return {"success": True, "message": f"成功出售 {quantity}份 {commodity_name}，获得 {total_earnings} 金币{urgency_msg}"}

    def sell_commodity_by_name(self, user_id: str, commodity_input: str) -> Dict[str, Any]:
        """按商品名称卖出所有该商品"""
        user = self.user_repo.get_by_id(user_id)
        if not user or not user.exchange_account_status:
            return {"success": False, "message": "您尚未开通交易所账户或用户不存在"}

        # 解析商品ID
        commodity_id = self._resolve_commodity_id(commodity_input)
        if not commodity_id:
            available_commodities = "、".join(self.name_to_id.keys())
            return {"success": False, "message": f"未找到商品 '{commodity_input}'，可用商品：{available_commodities}"}

        # 获取用户的所有该商品库存
        user_commodities = self.exchange_repo.get_user_commodities(user_id)
        target_commodities = [item for item in user_commodities if item.commodity_id == commodity_id]
        
        if not target_commodities:
            commodity_name = self.commodities[commodity_id].name
            return {"success": False, "message": f"您没有 {commodity_name} 库存"}

        # 获取当前市场价格
        market_status = self.get_market_status()
        current_price = market_status["prices"].get(commodity_id)
        if not current_price:
            return {"success": False, "message": "该商品今日无报价，无法出售"}

        # 计算盈亏分析
        prices = {commodity_id: current_price}
        analysis = self._calculate_profit_loss_analysis(target_commodities, prices)
        
        # 计算总收益
        total_quantity = sum(item.quantity for item in target_commodities)
        total_earnings = current_price * total_quantity
        
        # 计算交易税
        tax_rate = self.config.get("tax_rate", 0.05)  # 从配置读取税率，默认5%
        tax_amount = int(total_earnings * tax_rate)
        net_earnings = total_earnings - tax_amount
        
        # 更新用户金币
        user.coins += net_earnings
        self.user_repo.update(user)

        # 记录税收日志
        if self.log_repo:
            from ..domain.models import TaxRecord
            tax_log = TaxRecord(
                tax_id=0,
                user_id=user_id,
                tax_amount=tax_amount,
                tax_rate=tax_rate,
                original_amount=total_earnings,
                balance_after=user.coins,
                tax_type="交易所卖出税",
                timestamp=datetime.now()
            )
            self.log_repo.add_tax_record(tax_log)

        # 删除所有该商品的库存
        for item in target_commodities:
            self.exchange_repo.delete_user_commodity(item.instance_id)

        # 构建详细的消息
        commodity_name = self.commodities[commodity_id].name
        profit_status = "📈盈利" if analysis["profit_loss"] > 0 else "📉亏损" if analysis["profit_loss"] < 0 else "➖持平"
        
        message_parts = [
            f"✅ 成功出售所有 {total_quantity}份 {commodity_name}",
            f"💰 获得 {net_earnings} 金币（已扣除 {tax_amount} 交易税）",
            f"",
            f"📊 盈亏分析：",
            f"• 总成本：{analysis['total_cost']} 金币",
            f"• 总收入：{analysis['total_revenue']} 金币", 
            f"• 净盈亏：{analysis['profit_loss']:+} 金币 {profit_status}",
            f"• 盈利率：{analysis['profit_rate']:+.1f}%"
        ]
        
        return {"success": True, "message": "\n".join(message_parts)}

    def clear_all_inventory(self, user_id: str) -> Dict[str, Any]:
        """清空用户所有大宗商品库存"""
        user = self.user_repo.get_by_id(user_id)
        if not user or not user.exchange_account_status:
            return {"success": False, "message": "您尚未开通交易所账户或用户不存在"}

        # 获取用户的所有库存
        user_commodities = self.exchange_repo.get_user_commodities(user_id)
        
        if not user_commodities:
            return {"success": False, "message": "您的交易所库存为空"}

        # 获取当前市场价格
        market_status = self.get_market_status()
        prices = market_status["prices"]
        
        # 计算盈亏分析
        analysis = self._calculate_profit_loss_analysis(user_commodities, prices)
        
        total_earnings = 0
        sold_items = []
        
        # 计算总收益和统计信息
        for item in user_commodities:
            current_price = prices.get(item.commodity_id, 0)
            if current_price > 0:
                item_earnings = current_price * item.quantity
                total_earnings += item_earnings
                commodity_name = self.commodities[item.commodity_id].name
                sold_items.append(f"{item.quantity}份{commodity_name}")
            else:
                commodity_name = self.commodities[item.commodity_id].name
                sold_items.append(f"{item.quantity}份{commodity_name}(无报价)")

        # 计算交易税
        tax_rate = self.config.get("tax_rate", 0.05)  # 从配置读取税率，默认5%
        tax_amount = int(total_earnings * tax_rate)
        net_earnings = total_earnings - tax_amount

        # 更新用户金币
        user.coins += net_earnings
        self.user_repo.update(user)

        # 记录税收日志
        if self.log_repo:
            from ..domain.models import TaxRecord
            tax_log = TaxRecord(
                tax_id=0,
                user_id=user_id,
                tax_amount=tax_amount,
                tax_rate=tax_rate,
                original_amount=total_earnings,
                balance_after=user.coins,
                tax_type="交易所清仓税",
                timestamp=datetime.now()
            )
            self.log_repo.add_tax_record(tax_log)

        # 删除所有库存
        for item in user_commodities:
            self.exchange_repo.delete_user_commodity(item.instance_id)

        # 构建详细的消息
        sold_items_str = "、".join(sold_items)
        profit_status = "📈盈利" if analysis["profit_loss"] > 0 else "📉亏损" if analysis["profit_loss"] < 0 else "➖持平"
        
        message_parts = [
            f"✅ 清仓完成！出售了 {sold_items_str}",
            f"💰 获得 {net_earnings} 金币（已扣除 {tax_amount} 交易税）",
            f"",
            f"📊 盈亏分析：",
            f"• 总成本：{analysis['total_cost']} 金币",
            f"• 总收入：{analysis['total_revenue']} 金币",
            f"• 净盈亏：{analysis['profit_loss']:+} 金币 {profit_status}",
            f"• 盈利率：{analysis['profit_rate']:+.1f}%"
        ]
        
        # 添加详细分析（如果有多个商品）
        if len(analysis['details']) > 1:
            message_parts.extend([
                f"",
                f"📋 详细分析："
            ])
            for detail in analysis['details']:
                message_parts.append(f"• {detail['name']}: {detail['quantity']}份 {detail['status']} {detail['profit_loss']:+}金币 ({detail['profit_rate']:+.1f}%)")
        
        return {"success": True, "message": "\n".join(message_parts)}

    def clear_expired_commodities(self, user_id: str) -> None:
        user_commodities = self.exchange_repo.get_user_commodities(user_id)
        now = datetime.now()
        for item in user_commodities:
            if item.expires_at < now:
                self.exchange_repo.delete_user_commodity(item.instance_id)

    def start_daily_price_update_task(self):
        """启动每日价格更新任务"""
        if self._price_update_task is None or self._price_update_task.done():
            self._price_update_task = asyncio.create_task(self._daily_price_update_loop())

    def stop_daily_price_update_task(self):
        """停止每日价格更新任务"""
        if self._price_update_task and not self._price_update_task.done():
            self._price_update_task.cancel()
    
    def force_update_prices(self) -> Dict[str, Any]:
        """手动强制更新价格（用于测试和调试）"""
        try:
            logger.info("手动触发价格更新...")
            self.update_daily_prices()
            
            # 获取更新后的价格
            today_str = datetime.now().strftime("%Y-%m-%d")
            prices = self.exchange_repo.get_prices_for_date(today_str)
            price_data = {p.commodity_id: p.price for p in prices}
            
            return {
                "success": True, 
                "message": "价格更新成功",
                "prices": price_data,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            logger.error(f"手动价格更新失败: {e}")
            return {
                "success": False,
                "message": f"价格更新失败: {str(e)}"
            }

    async def _daily_price_update_loop(self):
        """每日价格更新循环 - 白天两次刷新：上午9点、下午3点、晚上9点"""
        logger.info("交易所价格更新任务已启动")
        while True:
            try:
                now = datetime.now()
                logger.info(f"价格更新任务检查时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 计算下一个更新时间（上午9点、下午3点或晚上9点）
                morning_update = now.replace(hour=9, minute=0, second=0, microsecond=0)
                afternoon_update = now.replace(hour=15, minute=0, second=0, microsecond=0)
                evening_update = now.replace(hour=21, minute=0, second=0, microsecond=0)
                
                next_update = None
                if now.hour < 9:
                    # 还没到上午9点，等待上午9点
                    next_update = morning_update
                elif now.hour < 15:
                    # 上午9点已过，但还没到下午3点，等待下午3点
                    next_update = afternoon_update
                elif now.hour < 21:
                    # 下午3点已过，但还没到晚上9点，等待晚上9点
                    next_update = evening_update
                else:
                    # 晚上9点已过，等待明天的上午9点
                    next_update = morning_update + timedelta(days=1)
                
                logger.info(f"下次价格更新时间: {next_update.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 等待到下一个更新时间
                wait_seconds = (next_update - now).total_seconds()
                logger.info(f"等待 {wait_seconds:.0f} 秒后更新价格")
                await asyncio.sleep(wait_seconds)
                
                # 更新价格
                logger.info("开始执行价格更新...")
                self.update_daily_prices()
                logger.info("价格更新完成")
                
            except asyncio.CancelledError:
                logger.info("价格更新任务被取消")
                break
            except Exception as e:
                # 记录错误但继续运行
                logger.error(f"交易所价格更新任务出错: {e}")
                await asyncio.sleep(3600)  # 出错后等待1小时再重试
    
    def _get_daily_fish_oil_expiry_days(self) -> int:
        """获取今日鱼油的固定腐败天数（1-3天循环）"""
        # 使用日期作为种子，确保同一天的所有鱼油腐败时间相同
        today = datetime.now().date()
        # 使用日期的天数作为种子，实现1-3天的循环
        day_of_year = today.timetuple().tm_yday
        return (day_of_year % 3) + 1  # 1, 2, 3 循环

    def _get_user_total_commodity_quantity(self, user_id: str) -> int:
        """获取用户所有大宗商品总数量（包括交易所库存和市场上架的商品）"""
        # 交易所库存中的大宗商品
        user_commodities = self.exchange_repo.get_user_commodities(user_id)
        inventory_quantity = sum(item.quantity for item in user_commodities)
        
        # 市场上架的大宗商品
        market_quantity = 0
        try:
            # 获取用户在市场上的所有大宗商品
            from ..repositories.sqlite_market_repo import SQLiteMarketRepository
            market_repo = SQLiteMarketRepository(self.exchange_repo.db_path)
            market_listings = market_repo.get_user_listings(user_id)
            for listing in market_listings:
                if listing.item_type == "commodity":
                    market_quantity += listing.quantity
        except Exception:
            # 如果获取市场数据失败，只计算库存数量
            pass
            
        return inventory_quantity + market_quantity

    def _calculate_profit_loss_analysis(self, commodities: List, current_prices: Dict[int, int]) -> Dict[str, Any]:
        """计算盈亏分析"""
        total_cost = 0  # 总成本
        total_revenue = 0  # 总收入
        profit_loss = 0  # 盈亏
        profit_rate = 0.0  # 盈利率
        details = []  # 详细分析
        
        for item in commodities:
            try:
                # 安全获取商品信息
                commodity = self.commodities.get(item.commodity_id)
                if not commodity:
                    logger.warning(f"商品ID {item.commodity_id} 不存在于商品列表中，跳过该项")
                    continue
                    
                commodity_name = commodity.name
                current_price = current_prices.get(item.commodity_id, 0)
                
                # 计算成本（买入价 * 数量）
                item_cost = item.purchase_price * item.quantity
                total_cost += item_cost
                
                # 计算收入（当前价 * 数量）
                item_revenue = current_price * item.quantity
                total_revenue += item_revenue
                
                # 计算单项盈亏
                item_profit_loss = item_revenue - item_cost
                item_profit_rate = (item_profit_loss / item_cost * 100) if item_cost > 0 else 0
                
                # 格式化单项信息
                profit_status = "📈盈利" if item_profit_loss > 0 else "📉亏损" if item_profit_loss < 0 else "➖持平"
                details.append({
                    "name": commodity_name,
                    "quantity": item.quantity,
                    "cost": item_cost,
                    "revenue": item_revenue,
                    "profit_loss": item_profit_loss,
                    "profit_rate": item_profit_rate,
                    "status": profit_status
                })
            except Exception as e:
                logger.error(f"计算商品 {item.commodity_id} 盈亏分析时出错: {e}")
                continue
        
        # 计算总体盈亏
        profit_loss = total_revenue - total_cost
        profit_rate = (profit_loss / total_cost * 100) if total_cost > 0 else 0
        
        return {
            "total_cost": total_cost,
            "total_revenue": total_revenue,
            "profit_loss": profit_loss,
            "profit_rate": profit_rate,
            "details": details
        }
