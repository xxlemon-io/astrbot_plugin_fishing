from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from astrbot.api import logger

from ..domain.models import User, UserCommodity
from ..repositories.abstract_repository import AbstractExchangeRepository, AbstractUserRepository, AbstractLogRepository


class ExchangeInventoryService:
    """交易所库存管理服务"""
    
    def __init__(self, user_repo: AbstractUserRepository, exchange_repo: AbstractExchangeRepository, 
                 config: Dict[str, Any], log_repo: AbstractLogRepository, market_service=None):
        self.user_repo = user_repo
        self.exchange_repo = exchange_repo
        self.log_repo = log_repo
        self.market_service = market_service
        self.config = config.get("exchange", {})
        
        # 商品定义
        self.commodities = {
            "dried_fish": {"name": "鱼干", "description": "经过晾晒处理的鱼类，保质期较长"},
            "fish_roe": {"name": "鱼卵", "description": "珍贵的鱼类卵子，营养价值极高"},
            "fish_oil": {"name": "鱼油", "description": "从鱼类中提取的油脂，用途广泛"}
        }

    def get_user_commodities(self, user_id: str) -> List[UserCommodity]:
        """获取用户的大宗商品库存"""
        return self.exchange_repo.get_user_commodities(user_id)

    def get_user_inventory(self, user_id: str) -> Dict[str, Any]:
        """获取用户库存信息"""
        try:
            inventory = self.get_user_commodities(user_id)
            
            # 按商品分组统计
            inventory_summary = {}
            for item in inventory:
                commodity_id = item.commodity_id
                if commodity_id not in inventory_summary:
                    inventory_summary[commodity_id] = {
                        "name": self.commodities[commodity_id]["name"],
                        "total_quantity": 0,
                        "total_cost": 0,
                        "items": []
                    }
                
                inventory_summary[commodity_id]["total_quantity"] += item.quantity
                inventory_summary[commodity_id]["total_cost"] += item.purchase_price * item.quantity
                inventory_summary[commodity_id]["items"].append({
                    "instance_id": item.instance_id,
                    "quantity": item.quantity,
                    "purchase_price": item.purchase_price,
                    "purchased_at": item.purchased_at,
                    "expires_at": item.expires_at
                })
            
            return {
                "success": True,
                "inventory": inventory_summary,
                "total_items": len(inventory)
            }
        except Exception as e:
            logger.error(f"获取用户库存失败: {e}")
            return {"success": False, "message": f"获取库存失败: {str(e)}"}

    def purchase_commodity(self, user_id: str, commodity_id: str, quantity: int, current_price: int) -> Dict[str, Any]:
        """购买大宗商品"""
        try:
            # 检查用户是否存在
            user = self.user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "message": "用户不存在"}
            
            # 检查商品是否存在
            if commodity_id not in self.commodities:
                return {"success": False, "message": "商品不存在"}
            
            # 计算总价格
            total_cost = current_price * quantity
            
            # 检查用户金币是否足够
            if user.coins < total_cost:
                return {"success": False, "message": f"金币不足，需要 {total_cost:,} 金币"}
            
            # 检查容量限制
            capacity = self.config.get("capacity", 1000)
            current_quantity = self._get_user_total_commodity_quantity(user_id)
            
            if current_quantity + quantity > capacity:
                return {"success": False, "message": f"超出容量限制，当前持仓: {current_quantity}/{capacity}"}
            
            # 扣除金币
            user.coins -= total_cost
            self.user_repo.update(user)
            
            # 添加商品到库存
            expires_at = datetime.now() + timedelta(days=7)  # 7天后腐败
            from ..domain.models import UserCommodity
            user_commodity = UserCommodity(
                instance_id=0,  # 临时值，数据库会自动生成
                user_id=user_id,
                commodity_id=commodity_id,
                quantity=quantity,
                purchase_price=current_price,
                purchased_at=datetime.now(),
                expires_at=expires_at
            )
            self.exchange_repo.add_user_commodity(user_commodity)
            
            return {
                "success": True,
                "message": f"购买成功！获得 {self.commodities[commodity_id]['name']} x{quantity}",
                "total_cost": total_cost,
                "current_price": current_price
            }
        except Exception as e:
            logger.error(f"购买大宗商品失败: {e}")
            return {"success": False, "message": f"购买失败: {str(e)}"}

    def sell_commodity(self, user_id: str, commodity_id: str, quantity: int, current_price: int) -> Dict[str, Any]:
        """卖出大宗商品"""
        try:
            # 检查用户是否存在
            user = self.user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "message": "用户不存在"}
            
            # 检查商品是否存在
            if commodity_id not in self.commodities:
                return {"success": False, "message": "商品不存在"}
            
            # 获取用户库存
            inventory = self.exchange_repo.get_user_commodities(user_id)
            commodity_items = [item for item in inventory if item.commodity_id == commodity_id]
            
            if not commodity_items:
                return {"success": False, "message": f"您没有 {self.commodities[commodity_id]['name']}"}
            
            # 计算可卖出数量
            available_quantity = sum(item.quantity for item in commodity_items)
            if available_quantity < quantity:
                return {"success": False, "message": f"库存不足，只有 {available_quantity} 个"}
            
            # 计算总收益
            total_income = current_price * quantity
            
            # 计算税费
            tax_rate = self.config.get("tax_rate", 0.05)
            tax_amount = int(total_income * tax_rate)
            net_income = total_income - tax_amount
            
            # 扣除库存
            remaining_quantity = quantity
            for item in commodity_items:
                if remaining_quantity <= 0:
                    break
                
                if item.quantity <= remaining_quantity:
                    # 完全消耗这个物品
                    self.exchange_repo.delete_user_commodity(item.instance_id)
                    remaining_quantity -= item.quantity
                else:
                    # 部分消耗
                    self.exchange_repo.update_user_commodity_quantity(item.instance_id, item.quantity - remaining_quantity)
                    remaining_quantity = 0
            
            # 添加金币
            user.coins += net_income
            self.user_repo.update(user)
            
            # 记录税费
            if self.log_repo:
                self.log_repo.add_tax_record(
                    user_id=user_id,
                    amount=tax_amount,
                    description=f"卖出 {self.commodities[commodity_id]['name']} x{quantity}"
                )
            
            # 计算盈亏分析
            profit_loss = self._calculate_profit_loss_analysis(commodity_items, quantity, current_price)
            
            return {
                "success": True,
                "message": f"卖出成功！获得 {net_income:,} 金币（含税费 {tax_amount:,} 金币）",
                "total_income": total_income,
                "tax_amount": tax_amount,
                "net_income": net_income,
                "current_price": current_price,
                "profit_loss": profit_loss
            }
        except Exception as e:
            logger.error(f"卖出大宗商品失败: {e}")
            return {"success": False, "message": f"卖出失败: {str(e)}"}

    def sell_commodity_by_instance(self, user_id: str, instance_id: int, quantity: int, current_price: int) -> Dict[str, Any]:
        """通过实例ID卖出大宗商品"""
        try:
            # 获取商品实例
            commodity_item = self.exchange_repo.get_user_commodity_by_instance_id(instance_id)
            if not commodity_item:
                return {"success": False, "message": "商品实例不存在"}
            
            # 检查数量
            if commodity_item.quantity < quantity:
                return {"success": False, "message": f"库存不足，只有 {commodity_item.quantity} 个"}
            
            # 调用通用卖出方法
            return self.sell_commodity(user_id, commodity_item.commodity_id, quantity, current_price)
        except Exception as e:
            logger.error(f"卖出大宗商品失败: {e}")
            return {"success": False, "message": f"卖出失败: {str(e)}"}

    def clear_all_inventory(self, user_id: str) -> Dict[str, Any]:
        """清空用户所有大宗商品库存"""
        try:
            # 检查用户是否存在
            user = self.user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "message": "用户不存在"}
            
            # 获取用户库存
            inventory = self.exchange_repo.get_user_commodities(user_id)
            if not inventory:
                return {"success": False, "message": "库存为空"}
            
            # 计算总价值
            total_value = 0
            for item in inventory:
                total_value += item.purchase_price * item.quantity
            
            # 计算税费
            tax_rate = self.config.get("tax_rate", 0.05)
            tax_amount = int(total_value * tax_rate)
            net_income = total_value - tax_amount
            
            # 清空库存
            for item in inventory:
                self.exchange_repo.delete_user_commodity(item.instance_id)
            
            # 添加金币
            user.coins += net_income
            self.user_repo.update(user)
            
            # 记录税费
            if self.log_repo:
                self.log_repo.add_tax_record(
                    user_id=user_id,
                    amount=tax_amount,
                    description="清仓所有大宗商品"
                )
            
            return {
                "success": True,
                "message": f"清仓成功！获得 {net_income:,} 金币（含税费 {tax_amount:,} 金币）",
                "total_value": total_value,
                "tax_amount": tax_amount,
                "net_income": net_income
            }
        except Exception as e:
            logger.error(f"清仓失败: {e}")
            return {"success": False, "message": f"清仓失败: {str(e)}"}

    def clear_commodity_inventory(self, user_id: str, commodity_id: str) -> Dict[str, Any]:
        """清空指定商品库存"""
        try:
            # 检查用户是否存在
            user = self.user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "message": "用户不存在"}
            
            # 检查商品是否存在
            if commodity_id not in self.commodities:
                return {"success": False, "message": "商品不存在"}
            
            # 获取指定商品库存
            inventory = self.exchange_repo.get_user_commodities(user_id)
            commodity_items = [item for item in inventory if item.commodity_id == commodity_id]
            
            if not commodity_items:
                return {"success": False, "message": f"您没有 {self.commodities[commodity_id]['name']}"}
            
            # 计算总价值
            total_value = sum(item.purchase_price * item.quantity for item in commodity_items)
            
            # 计算税费
            tax_rate = self.config.get("tax_rate", 0.05)
            tax_amount = int(total_value * tax_rate)
            net_income = total_value - tax_amount
            
            # 清空指定商品库存
            for item in commodity_items:
                self.exchange_repo.delete_user_commodity(item.instance_id)
            
            # 添加金币
            user.coins += net_income
            self.user_repo.update(user)
            
            # 记录税费
            if self.log_repo:
                self.log_repo.add_tax_record(
                    user_id=user_id,
                    amount=tax_amount,
                    description=f"清仓 {self.commodities[commodity_id]['name']}"
                )
            
            return {
                "success": True,
                "message": f"清仓成功！获得 {net_income:,} 金币（含税费 {tax_amount:,} 金币）",
                "total_value": total_value,
                "tax_amount": tax_amount,
                "net_income": net_income
            }
        except Exception as e:
            logger.error(f"清仓失败: {e}")
            return {"success": False, "message": f"清仓失败: {str(e)}"}

    def _get_user_total_commodity_quantity(self, user_id: str) -> int:
        """获取用户总的大宗商品数量（包括交易所库存和市场上架的商品）"""
        # 交易所库存数量
        inventory_quantity = 0
        inventory = self.exchange_repo.get_user_commodities(user_id)
        for item in inventory:
            inventory_quantity += item.quantity
        
        # 市场上架数量
        market_quantity = 0
        if self.market_service:
            try:
                # 获取用户所有上架商品
                user_listings_result = self.market_service.get_user_listings(user_id)
                if user_listings_result.get("success", False):
                    user_listings = user_listings_result.get("listings", [])
                    # 统计大宗商品数量
                    for listing in user_listings:
                        if listing.item_type == "commodity":
                            market_quantity += listing.quantity
            except Exception as e:
                logger.warning(f"获取用户市场商品数量失败: {e}")
        
        return inventory_quantity + market_quantity

    def _calculate_profit_loss_analysis(self, commodity_items: List[UserCommodity], sell_quantity: int, sell_price: int) -> Dict[str, Any]:
        """计算卖出时的盈亏分析"""
        total_cost = 0
        remaining_quantity = sell_quantity
        
        for item in commodity_items:
            if remaining_quantity <= 0:
                break
            
            item_quantity = min(item.quantity, remaining_quantity)
            total_cost += item.purchase_price * item_quantity
            remaining_quantity -= item_quantity
        
        total_income = sell_price * sell_quantity
        profit_loss = total_income - total_cost
        profit_rate = (profit_loss / total_cost * 100) if total_cost > 0 else 0
        
        return {
            "total_cost": total_cost,
            "total_income": total_income,
            "profit_loss": profit_loss,
            "profit_rate": profit_rate,
            "is_profit": profit_loss > 0
        }

    def calculate_holdings_profit_loss(self, user_commodities: List[UserCommodity], current_prices: Dict[str, int]) -> Dict[str, Any]:
        """计算持仓盈亏分析"""
        try:
            total_cost = 0
            total_current_value = 0
            
            for commodity in user_commodities:
                # 计算成本
                cost = commodity.purchase_price * commodity.quantity
                total_cost += cost
                
                # 计算当前价值
                current_price = current_prices.get(commodity.commodity_id, 0)
                current_value = current_price * commodity.quantity
                total_current_value += current_value
            
            # 计算盈亏
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
            logger.error(f"计算持仓盈亏分析失败: {e}")
            return {
                "total_cost": 0,
                "total_current_value": 0,
                "profit_loss": 0,
                "profit_rate": 0,
                "is_profit": False
            }

    def get_user_commodity_stats(self) -> Dict[str, Any]:
        """获取用户大宗商品统计"""
        try:
            # 获取所有用户的大宗商品数据
            all_commodities = self.exchange_repo.get_all_user_commodities()
            
            # 按商品分组统计
            commodity_stats = {}
            for commodity_id in self.commodities.keys():
                commodity_stats[commodity_id] = {
                    "name": self.commodities[commodity_id]["name"],
                    "total_quantity": 0,
                    "user_count": 0,
                    "average_quantity": 0,
                    "users": []
                }
            
            # 统计每个用户的数据
            user_stats = {}
            for commodity in all_commodities:
                user_id = commodity.user_id
                commodity_id = commodity.commodity_id
                
                if user_id not in user_stats:
                    user_stats[user_id] = {}
                
                if commodity_id not in user_stats[user_id]:
                    user_stats[user_id][commodity_id] = 0
                
                user_stats[user_id][commodity_id] += commodity.quantity
                commodity_stats[commodity_id]["total_quantity"] += commodity.quantity
            
            # 整理用户数据
            for user_id, user_commodities in user_stats.items():
                for commodity_id, quantity in user_commodities.items():
                    if quantity > 0:
                        commodity_stats[commodity_id]["user_count"] += 1
                        commodity_stats[commodity_id]["users"].append({
                            "user_id": user_id,
                            "quantity": quantity
                        })
            
            # 计算平均数量
            for commodity_id, stats in commodity_stats.items():
                if stats["user_count"] > 0:
                    stats["average_quantity"] = stats["total_quantity"] / stats["user_count"]
            
            # 计算总用户数和总持仓量
            total_users = len(user_stats)
            total_holdings = sum(stats["total_quantity"] for stats in commodity_stats.values())
            
            return {
                "success": True,
                "stats": {
                    "total_users": total_users,
                    "total_holdings": total_holdings,
                    "commodity_stats": commodity_stats
                }
            }
        except Exception as e:
            logger.error(f"获取用户大宗商品统计失败: {e}")
            return {"success": False, "message": str(e)}
