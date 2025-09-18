import random
from typing import Dict, Any
from datetime import timedelta

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractLogRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository
)
from ..domain.models import User, TaxRecord
from ..utils import get_now, get_today


class UserService:
    """封装与用户相关的业务逻辑"""

    def __init__(
        self,
        user_repo: AbstractUserRepository,
        log_repo: AbstractLogRepository,
        inventory_repo: AbstractInventoryRepository,
        item_template_repo: AbstractItemTemplateRepository,
        config: Dict[str, Any]  # 注入游戏配置
    ):
        self.user_repo = user_repo
        self.log_repo = log_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.config = config

    def register(self, user_id: str, nickname: str) -> Dict[str, Any]:
        """
        注册新用户。

        Args:
            user_id: 用户ID
            nickname: 用户昵称

        Returns:
            一个包含成功状态和消息的字典。
        """
        if self.user_repo.check_exists(user_id):
            return {"success": False, "message": "用户已注册"}

        initial_coins = self.config.get("user", {}).get("initial_coins", 200)
        new_user = User(
            user_id=user_id,
            nickname=nickname,
            coins=initial_coins,
            created_at=get_now()
        )
        self.user_repo.add(new_user)
        return {
            "success": True,
            "message": f"注册成功！欢迎 {nickname} 🎉 你获得了 {initial_coins} 金币作为起始资金。"
        }

    def create_user_for_admin(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """管理员创建用户，支持设置初始字段。"""
        user_id = data.get("user_id")
        if not user_id:
            return {"success": False, "message": "缺少 user_id"}

        if self.user_repo.check_exists(user_id):
            return {"success": False, "message": "用户已存在"}

        nickname = data.get("nickname")
        initial_coins = data.get("coins")
        if not isinstance(initial_coins, int):
            initial_coins = self.config.get("user", {}).get("initial_coins", 200)

        # 先最小化创建用户记录
        new_user = User(
            user_id=user_id,
            nickname=nickname,
            coins=initial_coins,
            created_at=get_now()
        )
        self.user_repo.add(new_user)

        # 组装可更新字段并复用更新逻辑
        allowed_fields = {
            'nickname', 'coins', 'premium_currency', 'total_fishing_count',
            'total_weight_caught', 'total_coins_earned', 'consecutive_login_days',
            'fish_pond_capacity', 'fishing_zone_id', 'auto_fishing_enabled'
        }
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        if updates:
            return self.update_user_for_admin(user_id, updates)
        return {"success": True, "message": "用户创建成功"}

    def get_leaderboard_data(self, limit: int = 10) -> Dict[str, Any]:
        """
        获取排行榜数据。

        Args:
            limit: 返回的用户数量限制

        Returns:
            包含排行榜数据的字典。
        """
        leaderboard_data = self.user_repo.get_leaderboard_data(limit)
        return {
            "success": True,
            "leaderboard": leaderboard_data
        }

    def daily_sign_in(self, user_id: str) -> Dict[str, Any]:
        """
        处理用户每日签到。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "请先注册才能签到"}

        today = get_today()
        if self.log_repo.has_checked_in(user_id, today):
            return {"success": False, "message": "你今天已经签到过了，明天再来吧！"}

        # 检查是否需要重置连续登录天数
        yesterday = today - timedelta(days=1)
        if not self.log_repo.has_checked_in(user_id, yesterday):
            user.consecutive_login_days = 0 # 不是连续签到，重置

        # 计算签到奖励
        signin_config = self.config.get("signin", {})
        min_reward = signin_config.get("min_reward", 100)
        max_reward = signin_config.get("max_reward", 300)
        coins_reward = random.randint(min_reward, max_reward)

        user.coins += coins_reward
        user.consecutive_login_days += 1
        user.last_login_time = get_now()

        # 检查连续签到奖励
        bonus_coins = 0
        consecutive_bonuses = signin_config.get("consecutive_bonuses", {})
        if str(user.consecutive_login_days) in consecutive_bonuses:
            bonus_coins = consecutive_bonuses[str(user.consecutive_login_days)]
            user.coins += bonus_coins

        # 更新数据库
        self.user_repo.update(user)
        self.log_repo.add_check_in(user_id, today)

        message = f"签到成功！获得 {coins_reward} 金币。"
        if bonus_coins > 0:
            message += f" 连续签到 {user.consecutive_login_days} 天，额外奖励 {bonus_coins} 金币！"

        return {
            "success": True,
            "message": message,
            "coins_reward": coins_reward,
            "bonus_coins": bonus_coins,
            "consecutive_days": user.consecutive_login_days
        }

    def get_user_current_accessory(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户当前装备的配件信息。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        current_accessory = self.inventory_repo.get_user_equipped_accessory(user_id)

        if not current_accessory:
            return {"success": True, "accessory": None}

        accessory_template = self.item_template_repo.get_accessory_by_id(current_accessory.accessory_id)
        if not accessory_template:
            return {"success": False, "message": "配件不存在"}

        return {
            "success": True,
            "accessory": {
                "id": current_accessory,
                "name": accessory_template.name,
                "description": accessory_template.description
            }
        }

    def get_user_titles(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户拥有的称号列表。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        owned_titles = self.inventory_repo.get_user_titles(user_id)
        if not owned_titles:
            return {"success": True, "titles": []}

        titles_data = []
        for title in owned_titles:
            title_template = self.item_template_repo.get_title_by_id(title)
            if title_template:
                titles_data.append({
                    "title_id": title,
                    "name": title_template.name,
                    "description": title_template.description,
                    "is_current": (title == user.current_title_id)
                })

        return {
            "success": True,
            "titles": titles_data
        }

    def use_title(self, user_id: str, title_id: int) -> Dict[str, Any]:
        """
        装备一个称号。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        owned_titles = self.inventory_repo.get_user_titles(user_id)
        if title_id not in list(owned_titles):
            return {"success": False, "message": "你没有这个称号，无法使用"}

        user.current_title_id = title_id
        self.user_repo.update(user)

        # 可以从ItemTemplateRepo获取称号名字来丰富返回信息
        title_template = self.item_template_repo.get_title_by_id(title_id)
        return {"success": True, "message": f"✅ 成功装备 {title_template.name}！"}

    def get_user_currency(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的货币信息。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在", "coins": 0, "premium_currency": 0}

        return {
            "success": True,
            "coins": user.coins,
            "premium_currency": user.premium_currency
        }

    def modify_user_coins(self, user_id: str, amount: int) -> Dict[str, Any]:
        """
        修改用户的金币数量。

        Args:
            user_id: 用户ID
            amount: 修改的金币数量

        Returns:
            包含成功状态和消息的字典。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        user.coins = amount
        self.user_repo.update(user)

        return {
            "success": True,
            "message": f"金币数量已更新，当前金币：{user.coins}"
        }

    def get_tax_record(self, user_id: str) -> Dict[str, Any]:
        """获取用户的税务记录。"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        tax_records = self.log_repo.get_tax_records(user_id)
        if not tax_records:
            return {"success": True, "records": []}
        records_data = []
        for record in tax_records:
            records_data.append({
                "amount": record.tax_amount,
                "timestamp": record.timestamp,
                "tax_type": record.tax_type,
            })
        return {
            "success": True,
            "records": records_data
        }

    def get_users_for_admin(self, page: int = 1, per_page: int = 20, search: str = None) -> Dict[str, Any]:
        """
        获取用户列表用于后台管理
        
        Args:
            page: 页码（从1开始）
            per_page: 每页数量
            search: 搜索关键词
            
        Returns:
            包含用户列表和分页信息的字典
        """
        offset = (page - 1) * per_page
        
        if search:
            users = self.user_repo.search_users(search, per_page, offset)
            total_count = self.user_repo.get_search_users_count(search)
        else:
            users = self.user_repo.get_all_users(per_page, offset)
            total_count = self.user_repo.get_users_count()
        
        # 计算分页信息
        total_pages = (total_count + per_page - 1) // per_page
        
        return {
            "success": True,
            "users": users,
            "pagination": {
                "current_page": page,
                "per_page": per_page,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages
            }
        }

    def get_user_details_for_admin(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户详细信息用于后台管理
        
        Args:
            user_id: 用户ID
            
        Returns:
            包含用户详细信息的字典
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        # 获取用户的装备信息
        equipped_rod = None
        if user.equipped_rod_instance_id:
            rod_instance = self.inventory_repo.get_user_rod_instance_by_id(user.user_id, user.equipped_rod_instance_id)
            if rod_instance:
                rod_template = self.item_template_repo.get_rod_by_id(rod_instance.rod_id)
                if rod_template:
                    equipped_rod = {
                        "name": rod_template.name,
                        "refine_level": rod_instance.refine_level
                    }
        
        equipped_accessory = None
        if user.equipped_accessory_instance_id:
            accessory_instance = self.inventory_repo.get_user_accessory_instance_by_id(user.user_id, user.equipped_accessory_instance_id)
            if accessory_instance:
                accessory_template = self.item_template_repo.get_accessory_by_id(accessory_instance.accessory_id)
                if accessory_template:
                    equipped_accessory = {
                        "name": accessory_template.name,
                        "refine_level": accessory_instance.refine_level
                    }
        
        current_title = None
        if user.current_title_id:
            title_template = self.item_template_repo.get_title_by_id(user.current_title_id)
            if title_template:
                current_title = title_template.name
        
        return {
            "success": True,
            "user": user,
            "equipped_rod": equipped_rod,
            "equipped_accessory": equipped_accessory,
            "current_title": current_title
        }

    def update_user_for_admin(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新用户信息（管理员操作）
        
        Args:
            user_id: 用户ID
            updates: 要更新的字段字典
            
        Returns:
            包含操作结果的字典
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        # 更新允许修改的字段
        allowed_fields = [
            'nickname', 'coins', 'premium_currency', 'total_fishing_count',
            'total_weight_caught', 'total_coins_earned', 'consecutive_login_days',
            'fish_pond_capacity', 'fishing_zone_id', 'auto_fishing_enabled'
        ]
        
        # 定义关键字段的校验逻辑
        def is_valid(field: str, value: Any) -> bool:
            numeric_non_negative = {
                'coins', 'premium_currency', 'total_fishing_count', 'total_weight_caught',
                'total_coins_earned', 'consecutive_login_days', 'fish_pond_capacity'
            }
            if field in numeric_non_negative:
                return isinstance(value, int) and value >= 0
            if field == 'fishing_zone_id':
                return isinstance(value, int) and (self.inventory_repo.get_zone_by_id(value) is not None)
            if field == 'auto_fishing_enabled':
                return isinstance(value, bool)
            if field == 'nickname':
                return (isinstance(value, str) and 0 < len(value) <= 32)
            return True

        for field, value in updates.items():
            if field in allowed_fields and hasattr(user, field):
                if not is_valid(field, value):
                    return {"success": False, "message": f"字段 {field} 的值无效: {value}"}
                setattr(user, field, value)
        
        self.user_repo.update(user)
        return {"success": True, "message": "用户信息更新成功"}

    def delete_user_for_admin(self, user_id: str) -> Dict[str, Any]:
        """
        删除用户（管理员操作）
        
        Args:
            user_id: 用户ID
            
        Returns:
            包含操作结果的字典
        """
        if not self.user_repo.check_exists(user_id):
            return {"success": False, "message": "用户不存在"}
        
        success = self.user_repo.delete_user(user_id)
        if success:
            return {"success": True, "message": "用户删除成功"}
        else:
            return {"success": False, "message": "用户删除失败"}

    def get_user_inventory_for_admin(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户物品库存信息（管理员操作）
        
        Args:
            user_id: 用户ID
            
        Returns:
            包含用户物品库存信息的字典
        """
        try:
            user = self.user_repo.get_by_id(user_id)
            if not user:
                return {"success": False, "message": "用户不存在"}
            
            # 获取鱼类库存
            fish_inventory = self.inventory_repo.get_fish_inventory(user_id)
            fish_data = []
            for item in fish_inventory:
                fish_template = self.item_template_repo.get_fish_by_id(item.fish_id)
                if fish_template:
                    fish_data.append({
                        "fish_id": item.fish_id,
                        "name": fish_template.name,
                        "rarity": fish_template.rarity,
                        "base_value": fish_template.base_value,
                        "quantity": item.quantity,
                        "total_value": fish_template.base_value * item.quantity
                    })
            
            # 获取鱼竿库存
            rod_instances = self.inventory_repo.get_user_rod_instances(user_id)
            rod_data = []
            for instance in rod_instances:
                rod_template = self.item_template_repo.get_rod_by_id(instance.rod_id)
                if rod_template:
                    rod_data.append({
                        "instance_id": instance.rod_instance_id,
                        "rod_id": instance.rod_id,
                        "name": rod_template.name,
                        "rarity": rod_template.rarity,
                        "refine_level": instance.refine_level,
                        "durability": instance.current_durability,
                        "is_equipped": instance.rod_instance_id == user.equipped_rod_instance_id
                    })
            
            # 获取饰品库存
            accessory_instances = self.inventory_repo.get_user_accessory_instances(user_id)
            accessory_data = []
            for instance in accessory_instances:
                accessory_template = self.item_template_repo.get_accessory_by_id(instance.accessory_id)
                if accessory_template:
                    accessory_data.append({
                        "instance_id": instance.accessory_instance_id,
                        "accessory_id": instance.accessory_id,
                        "name": accessory_template.name,
                        "rarity": accessory_template.rarity,
                        "refine_level": instance.refine_level,
                        "is_equipped": instance.accessory_instance_id == user.equipped_accessory_instance_id
                    })
            
            # 获取鱼饵库存
            bait_inventory = self.inventory_repo.get_user_bait_inventory(user_id)
            bait_data = []
            for bait_id, quantity in bait_inventory.items():
                bait_template = self.item_template_repo.get_bait_by_id(bait_id)
                if bait_template and quantity > 0:
                    bait_data.append({
                        "bait_id": bait_id,
                        "name": bait_template.name,
                        "rarity": bait_template.rarity,
                        "quantity": quantity,
                        "cost": bait_template.cost,
                        "total_value": bait_template.cost * quantity
                    })
            
            # 计算总价值
            fish_total_value = sum(item["total_value"] for item in fish_data)
            bait_total_value = sum(item["total_value"] for item in bait_data)
            
            return {
                "success": True,
                "user_id": user_id,
                "nickname": user.nickname,
                "fish_inventory": fish_data,
                "rod_inventory": rod_data,
                "accessory_inventory": accessory_data,
                "bait_inventory": bait_data,
                "stats": {
                    "fish_count": len(fish_data),
                    "rod_count": len(rod_data),
                    "accessory_count": len(accessory_data),
                    "bait_count": len(bait_data),
                    "fish_total_value": fish_total_value,
                    "bait_total_value": bait_total_value,
                    "total_inventory_value": fish_total_value + bait_total_value
                }
            }
        except Exception as e:
            return {"success": False, "message": f"获取库存信息时发生错误: {str(e)}"}

    def add_item_to_user_inventory(self, user_id: str, item_type: str, item_id: int, quantity: int = 1) -> Dict[str, Any]:
        """
        向用户库存添加物品（管理员操作）
        
        Args:
            user_id: 用户ID
            item_type: 物品类型 (fish, rod, accessory, bait)
            item_id: 物品ID
            quantity: 数量
            
        Returns:
            包含操作结果的字典
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        try:
            if item_type == "fish":
                fish_template = self.item_template_repo.get_fish_by_id(item_id)
                if not fish_template:
                    return {"success": False, "message": "鱼类不存在"}
                self.inventory_repo.add_fish_to_inventory(user_id, item_id, quantity)
                return {"success": True, "message": f"成功添加 {fish_template.name} x{quantity}"}
                
            elif item_type == "rod":
                rod_template = self.item_template_repo.get_rod_by_id(item_id)
                if not rod_template:
                    return {"success": False, "message": "鱼竿不存在"}
                for _ in range(quantity):
                    self.inventory_repo.add_rod_instance(user_id, item_id, rod_template.durability)
                return {"success": True, "message": f"成功添加 {rod_template.name} x{quantity}"}
                
            elif item_type == "accessory":
                accessory_template = self.item_template_repo.get_accessory_by_id(item_id)
                if not accessory_template:
                    return {"success": False, "message": "饰品不存在"}
                for _ in range(quantity):
                    self.inventory_repo.add_accessory_instance(user_id, item_id)
                return {"success": True, "message": f"成功添加 {accessory_template.name} x{quantity}"}
                
            elif item_type == "bait":
                bait_template = self.item_template_repo.get_bait_by_id(item_id)
                if not bait_template:
                    return {"success": False, "message": "鱼饵不存在"}
                self.inventory_repo.update_bait_quantity(user_id, item_id, quantity)
                return {"success": True, "message": f"成功添加 {bait_template.name} x{quantity}"}
                
            else:
                return {"success": False, "message": "不支持的物品类型"}
                
        except Exception as e:
            return {"success": False, "message": f"添加物品失败: {str(e)}"}

    def remove_item_from_user_inventory(self, user_id: str, item_type: str, item_id: int, quantity: int = 1) -> Dict[str, Any]:
        """
        从用户库存移除物品（管理员操作）
        
        Args:
            user_id: 用户ID
            item_type: 物品类型 (fish, rod, accessory, bait)
            item_id: 物品ID
            quantity: 数量
            
        Returns:
            包含操作结果的字典
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        
        try:
            if item_type == "fish":
                fish_template = self.item_template_repo.get_fish_by_id(item_id)
                if not fish_template:
                    return {"success": False, "message": "鱼类不存在"}
                # 检查库存数量
                fish_inventory = self.inventory_repo.get_fish_inventory(user_id)
                current_quantity = 0
                for item in fish_inventory:
                    if item.fish_id == item_id:
                        current_quantity = item.quantity
                        break
                
                if current_quantity < quantity:
                    return {"success": False, "message": f"库存不足，当前只有 {current_quantity} 个"}
                
                # 减少数量
                self.inventory_repo.update_fish_quantity(user_id, item_id, -quantity)
                return {"success": True, "message": f"成功移除 {fish_template.name} x{quantity}"}
                
            elif item_type == "rod":
                rod_template = self.item_template_repo.get_rod_by_id(item_id)
                if not rod_template:
                    return {"success": False, "message": "鱼竿不存在"}
                
                # 获取用户的所有该类型鱼竿实例
                rod_instances = self.inventory_repo.get_user_rod_instances(user_id)
                target_instances = [inst for inst in rod_instances if inst.rod_id == item_id]
                
                if len(target_instances) < quantity:
                    return {"success": False, "message": f"库存不足，当前只有 {len(target_instances)} 个"}
                
                # 删除指定数量的实例（优先删除未装备的）
                removed_count = 0
                for instance in target_instances:
                    if removed_count >= quantity:
                        break
                    # 如果正在装备，先取消装备
                    if instance.rod_instance_id == user.equipped_rod_instance_id:
                        user.equipped_rod_instance_id = None
                        self.user_repo.update(user)
                    # 删除实例
                    self.inventory_repo.delete_rod_instance(instance.rod_instance_id)
                    removed_count += 1
                
                return {"success": True, "message": f"成功移除 {rod_template.name} x{removed_count}"}
                
            elif item_type == "accessory":
                accessory_template = self.item_template_repo.get_accessory_by_id(item_id)
                if not accessory_template:
                    return {"success": False, "message": "饰品不存在"}
                
                # 获取用户的所有该类型饰品实例
                accessory_instances = self.inventory_repo.get_user_accessory_instances(user_id)
                target_instances = [inst for inst in accessory_instances if inst.accessory_id == item_id]
                
                if len(target_instances) < quantity:
                    return {"success": False, "message": f"库存不足，当前只有 {len(target_instances)} 个"}
                
                # 删除指定数量的实例（优先删除未装备的）
                removed_count = 0
                for instance in target_instances:
                    if removed_count >= quantity:
                        break
                    # 如果正在装备，先取消装备
                    if instance.accessory_instance_id == user.equipped_accessory_instance_id:
                        user.equipped_accessory_instance_id = None
                        self.user_repo.update(user)
                    # 删除实例
                    self.inventory_repo.delete_accessory_instance(instance.accessory_instance_id)
                    removed_count += 1
                
                return {"success": True, "message": f"成功移除 {accessory_template.name} x{removed_count}"}
                
            elif item_type == "bait":
                bait_template = self.item_template_repo.get_bait_by_id(item_id)
                if not bait_template:
                    return {"success": False, "message": "鱼饵不存在"}
                # 检查库存数量
                bait_inventory = self.inventory_repo.get_user_bait_inventory(user_id)
                current_quantity = bait_inventory.get(item_id, 0)
                
                if current_quantity < quantity:
                    return {"success": False, "message": f"库存不足，当前只有 {current_quantity} 个"}
                
                # 减少数量
                self.inventory_repo.update_bait_quantity(user_id, item_id, -quantity)
                return {"success": True, "message": f"成功移除 {bait_template.name} x{quantity}"}
                
            else:
                return {"success": False, "message": "不支持的物品类型"}
                
        except Exception as e:
            return {"success": False, "message": f"移除物品失败: {str(e)}"}