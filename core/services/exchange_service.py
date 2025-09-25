import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

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
    ):
        self.user_repo = user_repo
        self.exchange_repo = exchange_repo
        self.config = config.get("exchange", {})
        self.commodities = {c.commodity_id: c for c in self.exchange_repo.get_all_commodities()}
        # 创建中文名称到商品ID的映射
        self.name_to_id = {c.name: c.commodity_id for c in self.commodities.values()}
        self._price_update_task = None

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
        if self.exchange_repo.get_prices_for_date(today_str):
            return  # Prices already exist for today

        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        last_prices = {p.commodity_id: p.price for p in self.exchange_repo.get_prices_for_date(yesterday_str)}

        for commodity_id, commodity in self.commodities.items():
            last_price = last_prices.get(commodity_id, self.config.get("initial_prices", {}).get(commodity_id, 100))
            new_price = self._calculate_new_price(commodity_id, last_price)
            self.exchange_repo.add_exchange_price(Exchange(date=today_str, commodity_id=commodity_id, price=new_price))

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

        # 腐败机制：用户购入时计算腐败时间
        now = datetime.now()
        if commodity_id == 'dried_fish':
            expires_at = now + timedelta(days=3)
        elif commodity_id == 'fish_roe':
            expires_at = now + timedelta(days=2)
        elif commodity_id == 'fish_oil':
            days = random.randint(1, 3)
            expires_at = now + timedelta(days=days)
        else:
            return {"success": False, "message": "未知商品"}

        # 清理腐败仓库
        self.clear_expired_commodities(user_id)

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
            corruption_warning = "，1-3天后将腐败"
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

    def clear_expired_commodities(self, user_id: str) -> None:
        user_commodities = self.exchange_repo.get_user_commodities(user_id)
        now = datetime.now()
        for item in user_commodities:
            if item.expires_at < now:
                self.exchange_repo.delete_user_commodity(item.instance_id)

    def list_commodity_on_market(self, user_id: str, instance_id: int, quantity: int, price: int, is_anonymous: bool) -> Dict[str, Any]:
        from ..services.market_service import MarketService
        # ... this is complex and requires careful integration with MarketService.
        # For now, we'll just placeholder this functionality.
        return {"success": False, "message": "暂不支持将大宗商品上架到玩家市场"}

    def start_daily_price_update_task(self):
        """启动每日价格更新任务"""
        if self._price_update_task is None or self._price_update_task.done():
            self._price_update_task = asyncio.create_task(self._daily_price_update_loop())

    def stop_daily_price_update_task(self):
        """停止每日价格更新任务"""
        if self._price_update_task and not self._price_update_task.done():
            self._price_update_task.cancel()

    async def _daily_price_update_loop(self):
        """每日价格更新循环"""
        while True:
            try:
                # 计算到下一个9点的时间
                now = datetime.now()
                next_update = now.replace(hour=9, minute=0, second=0, microsecond=0)
                if now.hour >= 9:
                    next_update += timedelta(days=1)
                
                # 等待到下一个9点
                wait_seconds = (next_update - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                
                # 更新价格
                self.update_daily_prices()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # 记录错误但继续运行
                print(f"交易所价格更新任务出错: {e}")
                await asyncio.sleep(3600)  # 出错后等待1小时再重试
