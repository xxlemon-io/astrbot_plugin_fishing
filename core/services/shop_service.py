from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# 导入仓储接口
from ..repositories.abstract_repository import (
    AbstractItemTemplateRepository,
    AbstractInventoryRepository,
    AbstractUserRepository,
    AbstractShopRepository,
)
from ..domain.models import Shop, ShopItem, ShopItemCost, ShopItemReward


class ShopService:
    """封装与系统商店相关的业务逻辑（新设计：shops + shop_items）"""

    def __init__(
        self,
        item_template_repo: AbstractItemTemplateRepository,
        inventory_repo: AbstractInventoryRepository,
        user_repo: AbstractUserRepository,
        shop_repo: Optional[AbstractShopRepository] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.item_template_repo = item_template_repo
        self.inventory_repo = inventory_repo
        self.user_repo = user_repo
        self.shop_repo = shop_repo
        self.config = config or {}

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """解析时间字符串为 datetime 对象"""
        if not dt_str or not isinstance(dt_str, str):
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None

    def _check_shop_availability(self, shop: Dict[str, Any]) -> Optional[str]:
        """检查商店是否可用，返回错误消息或None"""
        if not shop.get("is_active", True):
            return "商店未启用"
        
        now = datetime.now()
        
        # 检查日期范围
        start_time = self._parse_datetime(shop.get("start_time"))
        end_time = self._parse_datetime(shop.get("end_time"))
        if start_time and now < start_time:
            return "商店尚未开放"
        if end_time and now > end_time:
            return "商店已关闭"
        
        # 检查每日时段
        daily_start = shop.get("daily_start_time")
        daily_end = shop.get("daily_end_time")
        if daily_start and daily_end:
            current_time = now.time()
            try:
                start_hour, start_min = map(int, daily_start.split(":"))
                end_hour, end_min = map(int, daily_end.split(":"))
                start_time_today = datetime.combine(now.date(), datetime.min.time().replace(hour=start_hour, minute=start_min))
                end_time_today = datetime.combine(now.date(), datetime.min.time().replace(hour=end_hour, minute=end_min))
                
                if not (start_time_today <= now <= end_time_today):
                    return f"商店营业时间：{daily_start}-{daily_end}"
            except (ValueError, IndexError):
                pass  # 忽略时间格式错误
        
        return None

    def _check_item_availability(self, item: Dict[str, Any]) -> Optional[str]:
        """检查商品是否可用，返回错误消息或None"""
        if not item.get("is_active", True):
            return "商品未启用"
        
        now = datetime.now()
        
        # 检查时间范围
        start_time = self._parse_datetime(item.get("start_time"))
        end_time = self._parse_datetime(item.get("end_time"))
        if start_time and now < start_time:
            return "商品尚未开售"
        if end_time and now > end_time:
            return "商品已过期"
        
        return None

    # ---- 商店管理 ----
    def get_shops(self) -> Dict[str, Any]:
        """获取所有活跃商店"""
        if not self.shop_repo:
            return {"success": True, "shops": []}
        
        shops = self.shop_repo.get_active_shops()
        return {"success": True, "shops": shops}

    def get_shop_details(self, shop_id: int) -> Dict[str, Any]:
        """获取商店详情和商品列表"""
        if not self.shop_repo:
            return {"success": False, "message": "商店系统未初始化"}
        
        shop = self.shop_repo.get_shop_by_id(shop_id)
        if not shop:
            return {"success": False, "message": "商店不存在"}
        
        # 检查商店可用性
        availability_error = self._check_shop_availability(shop)
        if availability_error:
            return {"success": False, "message": availability_error}
        
        # 获取商店商品
        items = self.shop_repo.get_shop_items(shop_id)
        items_with_details = []
        
        for item in items:
            # 检查商品可用性
            item_error = self._check_item_availability(item)
            if item_error:
                continue  # 跳过不可用的商品
            
            # 获取成本和奖励
            costs = self.shop_repo.get_item_costs(item["item_id"])
            rewards = self.shop_repo.get_item_rewards(item["item_id"])
            
            items_with_details.append({
                "item": item,
                "costs": costs,
                "rewards": rewards,
            })
        
        return {
            "success": True,
            "shop": shop,
            "items": items_with_details
        }

    # ---- 商品购买 ----
    def purchase_item(self, user_id: str, item_id: int, quantity: int = 1) -> Dict[str, Any]:
        """购买商店商品"""
        if not self.shop_repo:
            return {"success": False, "message": "商店系统未初始化"}
        
        if quantity <= 0:
            return {"success": False, "message": "数量必须大于0"}
        
        # 获取商品信息
        item = self.shop_repo.get_shop_item_by_id(item_id)
        if not item:
            return {"success": False, "message": "商品不存在"}
        
        # 检查商品可用性
        item_error = self._check_item_availability(item)
        if item_error:
            return {"success": False, "message": item_error}
        
        # 获取商店信息并检查可用性
        shop = self.shop_repo.get_shop_by_id(item["shop_id"])
        if not shop:
            return {"success": False, "message": "商店不存在"}
        
        shop_error = self._check_shop_availability(shop)
        if shop_error:
            return {"success": False, "message": shop_error}
        
        # 获取用户信息
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        # 库存检查
        if item.get("stock_total") is not None:
            available_stock = item["stock_total"] - item.get("stock_sold", 0)
            if available_stock < quantity:
                return {"success": False, "message": f"库存不足，剩余 {available_stock} 个"}
        
        # 限购检查
        if item.get("per_user_limit") is not None:
            purchased_total = self.shop_repo.get_user_purchased_count(user_id, item_id)
            if purchased_total + quantity > item["per_user_limit"]:
                remaining = item["per_user_limit"] - purchased_total
                return {"success": False, "message": f"超过个人限购，还可购买 {remaining} 个"}
        
        if item.get("per_user_daily_limit") is not None and item["per_user_daily_limit"] > 0:
            start_of_day = datetime(datetime.now().year, datetime.now().month, datetime.now().day)
            purchased_today = self.shop_repo.get_user_purchased_count(user_id, item_id, since=start_of_day)
            if purchased_today + quantity > item["per_user_daily_limit"]:
                remaining = item["per_user_daily_limit"] - purchased_today
                return {"success": False, "message": f"超过今日限购，今日还可购买 {remaining} 个"}
        
        # 计算成本
        costs = self.shop_repo.get_item_costs(item_id)
        cost_result = self._calculate_costs(costs, quantity)
        if not cost_result["success"]:
            return cost_result
        
        # 检查用户资源
        cost_check = self._check_user_resources(user, cost_result["costs"])
        if not cost_check["success"]:
            return cost_check
        
        # 扣除成本
        self._deduct_costs(user, cost_result["costs"])
        
        # 发放奖励
        rewards = self.shop_repo.get_item_rewards(item_id)
        obtained_items = self._give_rewards(user_id, rewards, quantity)
        
        # 更新销量和记录
        self.shop_repo.increase_item_sold(item_id, quantity)
        self.shop_repo.add_purchase_record(user_id, item_id, quantity)
        
        # 构建成功消息
        success_message = f"✅ 购买成功：{item['name']} x{quantity}"
        if obtained_items:
            unique_items = list(set(obtained_items))
            success_message += f"\n📦 获得物品：\n" + "\n".join([f"  • {item}" for item in unique_items])
        
        return {"success": True, "message": success_message}

    def _calculate_costs(self, costs: List[Dict[str, Any]], quantity: int) -> Dict[str, Any]:
        """计算总成本，支持AND/OR关系"""
        if not costs:
            return {"success": True, "costs": {}}
        
        # 按组分组成本
        groups = {}
        for cost in costs:
            group_id = cost.get("group_id", 0)
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(cost)
        
        total_costs = {
            "coins": 0,
            "premium": 0,
            "items": {},
            "fish": {}
        }
        
        # 处理每个组
        for group_id, group_costs in groups.items():
            if len(group_costs) == 1:
                # 单个成本，直接添加
                cost = group_costs[0]
                cost_type = cost["cost_type"]
                amount = cost["cost_amount"] * quantity
                
                if cost_type == "coins":
                    total_costs["coins"] += amount
                elif cost_type == "premium":
                    total_costs["premium"] += amount
                elif cost_type == "item":
                    item_id = cost.get("cost_item_id")
                    if item_id:
                        total_costs["items"][item_id] = total_costs["items"].get(item_id, 0) + amount
                elif cost_type == "fish":
                    fish_id = cost.get("cost_item_id")
                    if fish_id:
                        total_costs["fish"][fish_id] = total_costs["fish"].get(fish_id, 0) + amount
            else:
                # 多个成本，检查关系
                relation = group_costs[0].get("cost_relation", "and")
                if relation == "and":
                    # AND关系：所有成本都需要
                    for cost in group_costs:
                        cost_type = cost["cost_type"]
                        amount = cost["cost_amount"] * quantity
                        
                        if cost_type == "coins":
                            total_costs["coins"] += amount
                        elif cost_type == "premium":
                            total_costs["premium"] += amount
                        elif cost_type == "item":
                            item_id = cost.get("cost_item_id")
                            if item_id:
                                total_costs["items"][item_id] = total_costs["items"].get(item_id, 0) + amount
                        elif cost_type == "fish":
                            fish_id = cost.get("cost_item_id")
                            if fish_id:
                                total_costs["fish"][fish_id] = total_costs["fish"].get(fish_id, 0) + amount
                elif relation == "or":
                    # OR关系：选择最便宜的成本（这里简化处理，选择第一个）
                    cost = group_costs[0]
                    cost_type = cost["cost_type"]
                    amount = cost["cost_amount"] * quantity
                    
                    if cost_type == "coins":
                        total_costs["coins"] += amount
                    elif cost_type == "premium":
                        total_costs["premium"] += amount
                    elif cost_type == "item":
                        item_id = cost.get("cost_item_id")
                        if item_id:
                            total_costs["items"][item_id] = total_costs["items"].get(item_id, 0) + amount
                    elif cost_type == "fish":
                        fish_id = cost.get("cost_item_id")
                        if fish_id:
                            total_costs["fish"][fish_id] = total_costs["fish"].get(fish_id, 0) + amount
        
        return {"success": True, "costs": total_costs}

    def _check_user_resources(self, user: Any, costs: Dict[str, Any]) -> Dict[str, Any]:
        """检查用户是否有足够资源"""
        # 检查金币
        if costs.get("coins", 0) > 0 and user.coins < costs["coins"]:
            return {"success": False, "message": f"金币不足，需要 {costs['coins']} 金币"}
        
        # 检查高级货币
        if costs.get("premium", 0) > 0 and user.premium_currency < costs["premium"]:
            return {"success": False, "message": f"高级货币不足，需要 {costs['premium']}"}
        
        # 检查道具
        if costs.get("items"):
            inv_items = self.inventory_repo.get_user_item_inventory(user.user_id)
            for item_id, need_qty in costs["items"].items():
                if inv_items.get(item_id, 0) < need_qty:
                    tpl = self.item_template_repo.get_item_by_id(item_id)
                    name = tpl.name if tpl else str(item_id)
                    return {"success": False, "message": f"道具不足：{name} x{need_qty}"}
        
        # 检查鱼类
        if costs.get("fish"):
            inv_fish = self.inventory_repo.get_fish_inventory(user.user_id)
            fish_counts = {fish_item.fish_id: fish_item.quantity for fish_item in inv_fish}
            
            for fish_id, need_qty in costs["fish"].items():
                if fish_counts.get(fish_id, 0) < need_qty:
                    fish_tpl = self.item_template_repo.get_fish_by_id(fish_id)
                    name = fish_tpl.name if fish_tpl else str(fish_id)
                    return {"success": False, "message": f"鱼类不足：{name} x{need_qty}"}
        
        return {"success": True}

    def _deduct_costs(self, user: Any, costs: Dict[str, Any]) -> None:
        """扣除用户资源"""
        # 扣除金币
        if costs.get("coins", 0) > 0:
            user.coins -= costs["coins"]
        
        # 扣除高级货币
        if costs.get("premium", 0) > 0:
            user.premium_currency -= costs["premium"]
        
        # 更新用户
        self.user_repo.update(user)
        
        # 扣除道具
        if costs.get("items"):
            for item_id, need_qty in costs["items"].items():
                self.inventory_repo.decrease_item_quantity(user.user_id, item_id, need_qty)
        
        # 扣除鱼类
        if costs.get("fish"):
            for fish_id, need_qty in costs["fish"].items():
                self.inventory_repo.update_fish_quantity(user.user_id, fish_id, -need_qty)

    def _give_rewards(self, user_id: str, rewards: List[Dict[str, Any]], quantity: int) -> List[str]:
        """发放奖励并返回获得的物品列表"""
        obtained_items = []
        
        for _ in range(quantity):
            for reward in rewards:
                reward_type = reward["reward_type"]
                reward_item_id = reward.get("reward_item_id")
                reward_quantity = reward.get("reward_quantity", 1)
                reward_refine_level = reward.get("reward_refine_level")
                
                if reward_type == "rod" and reward_item_id:
                    rod_tpl = self.item_template_repo.get_rod_by_id(reward_item_id)
                    self.inventory_repo.add_rod_instance(
                        user_id=user_id,
                        rod_id=reward_item_id,
                        durability=rod_tpl.durability if rod_tpl else None,
                        refine_level=reward_refine_level or 1,
                    )
                    if rod_tpl:
                        obtained_items.append(f"🎣 {rod_tpl.name}")
                
                elif reward_type == "accessory" and reward_item_id:
                    accessory_tpl = self.item_template_repo.get_accessory_by_id(reward_item_id)
                    self.inventory_repo.add_accessory_instance(
                        user_id, reward_item_id, refine_level=reward_refine_level or 1
                    )
                    if accessory_tpl:
                        obtained_items.append(f"💍 {accessory_tpl.name}")
                
                elif reward_type == "bait" and reward_item_id:
                    bait_tpl = self.item_template_repo.get_bait_by_id(reward_item_id)
                    self.inventory_repo.update_bait_quantity(user_id, reward_item_id, reward_quantity)
                    if bait_tpl:
                        obtained_items.append(f"🪱 {bait_tpl.name} x{reward_quantity}")
                
                elif reward_type == "item" and reward_item_id:
                    item_tpl = self.item_template_repo.get_item_by_id(reward_item_id)
                    self.inventory_repo.update_item_quantity(user_id, reward_item_id, reward_quantity)
                    if item_tpl:
                        obtained_items.append(f"🎁 {item_tpl.name} x{reward_quantity}")
                
                elif reward_type == "fish" and reward_item_id:
                    fish_tpl = self.item_template_repo.get_fish_by_id(reward_item_id)
                    self.inventory_repo.update_fish_quantity(user_id, reward_item_id, reward_quantity)
                    if fish_tpl:
                        obtained_items.append(f"🐟 {fish_tpl.name} x{reward_quantity}")
                
                elif reward_type == "coins":
                    # 直接给用户加金币
                    user = self.user_repo.get_by_id(user_id)
                    if user:
                        user.coins += reward_quantity
                        self.user_repo.update(user)
                        obtained_items.append(f"💰 金币 x{reward_quantity}")
        
        return obtained_items

    # ---- 兼容性方法（向后兼容旧系统） ----
    def get_shop_listings(self) -> Dict[str, Any]:
        """获取商店商品列表（兼容旧接口）"""
        result: Dict[str, Any] = {"success": True}
        if not self.shop_repo:
            result["offers"] = []
            return result
        
        offers = self.shop_repo.get_active_offers()
        offers_view: List[Dict[str, Any]] = []
        
        for offer in offers:
            costs = self.shop_repo.get_item_costs(offer["item_id"])
            rewards = self.shop_repo.get_item_rewards(offer["item_id"])
            offers_view.append({
                "offer": offer,
                "costs": costs,
                "rewards": rewards,
            })
        
        result["offers"] = offers_view
        return result

    def buy_item(self, user_id: str, item_type: str, item_template_id: int, quantity: int = 1) -> Dict[str, Any]:
        """旧商店购买接口（已废弃）"""
        return {"success": False, "message": "旧商店购买已废弃，请使用新的商店系统"}

    def purchase_offer(self, user_id: str, offer_id: int, quantity: int = 1) -> Dict[str, Any]:
        """购买商品（兼容旧接口）"""
        return self.purchase_item(user_id, offer_id, quantity)

    def purchase_in_shop(self, user_id: str, shop_id: int, offer_id: int, quantity: int = 1) -> Dict[str, Any]:
        """在指定商店购买商品（兼容旧接口）"""
        return self.purchase_item(user_id, offer_id, quantity)