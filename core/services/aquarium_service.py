from typing import Dict, Any, List, Optional
from datetime import datetime

from ..repositories.abstract_repository import AbstractInventoryRepository, AbstractUserRepository, AbstractItemTemplateRepository
from ..domain.models import User, UserAquariumItem, AquariumUpgrade, Fish


class AquariumService:
    """水族箱服务，处理水族箱相关的业务逻辑"""

    def __init__(self, inventory_repo: AbstractInventoryRepository, 
                 user_repo: AbstractUserRepository, 
                 item_template_repo: AbstractItemTemplateRepository):
        self.inventory_repo = inventory_repo
        self.user_repo = user_repo
        self.item_template_repo = item_template_repo

    def get_user_aquarium(self, user_id: str) -> Dict[str, Any]:
        """获取用户水族箱信息"""
        aquarium_items = self.inventory_repo.get_aquarium_inventory(user_id)
        total_value = self.inventory_repo.get_aquarium_inventory_value(user_id)
        total_count = self.inventory_repo.get_aquarium_total_count(user_id)

        # 获取用户信息以获取容量
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 为了丰富信息，可以从模板仓储获取鱼的详细信息
        enriched_items = []
        for item in aquarium_items:
            if fish_template := self.item_template_repo.get_fish_by_id(item.fish_id):
                # 计算实际价值（高品质鱼双倍价值）
                actual_value = fish_template.base_value * (1 + item.quality_level)
                enriched_items.append({
                    "fish_id": item.fish_id,
                    "name": fish_template.name,
                    "rarity": fish_template.rarity,
                    "base_value": fish_template.base_value,
                    "quantity": item.quantity,
                    "quality_level": item.quality_level,  # 添加品质等级
                    "actual_value": actual_value,  # 添加实际价值
                    "quality_label": "✨高品质" if item.quality_level == 1 else "普通",  # 添加品质标签
                    "added_at": item.added_at
                })

        return {
            "success": True,
            "fishes": enriched_items,
            "stats": {
                "total_count": total_count,
                "total_value": total_value,
                "capacity": user.aquarium_capacity,
                "available_space": user.aquarium_capacity - total_count
            }
        }

    def add_fish_to_aquarium(self, user_id: str, fish_id: int, quantity: int = 1, quality_level: int = 0) -> Dict[str, Any]:
        """将鱼添加到水族箱"""
        # 检查用户是否存在
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 检查鱼是否存在
        fish_template = self.item_template_repo.get_fish_by_id(fish_id)
        if not fish_template:
            return {"success": False, "message": "鱼类不存在"}

        # 检查水族箱容量
        current_count = self.inventory_repo.get_aquarium_total_count(user_id)
        if current_count + quantity > user.aquarium_capacity:
            return {
                "success": False, 
                "message": f"水族箱容量不足！当前容量：{user.aquarium_capacity}，已有：{current_count}，需要：{quantity}"
            }

        # 检查鱼塘中是否有足够的鱼（指定品质）
        fish_inventory = self.inventory_repo.get_fish_inventory(user_id)
        fish_item = next((item for item in fish_inventory if item.fish_id == fish_id and item.quality_level == quality_level), None)
        if not fish_item or fish_item.quantity < quantity:
            quality_label = "✨高品质" if quality_level == 1 else "普通"
            return {"success": False, "message": f"鱼塘中没有足够的{quality_label}{fish_template.name}"}

        # 从鱼塘移除鱼，添加到水族箱（保持品质）
        self.inventory_repo.update_fish_quantity(user_id, fish_id, -quantity, quality_level)
        self.inventory_repo.add_fish_to_aquarium(user_id, fish_id, quantity, quality_level)

        quality_label = "✨高品质" if quality_level == 1 else "普通"
        return {
            "success": True, 
            "message": f"成功将 {quality_label}{fish_template.name} x{quantity} 放入水族箱！"
        }

    def remove_fish_from_aquarium(self, user_id: str, fish_id: int, quantity: int = 1, quality_level: int = 0) -> Dict[str, Any]:
        """从水族箱移除鱼到鱼塘"""
        # 检查用户是否存在
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 检查鱼是否存在
        fish_template = self.item_template_repo.get_fish_by_id(fish_id)
        if not fish_template:
            return {"success": False, "message": "鱼类不存在"}

        # 检查水族箱中是否有足够的鱼（指定品质）
        aquarium_items = self.inventory_repo.get_aquarium_inventory(user_id)
        fish_item = next((item for item in aquarium_items if item.fish_id == fish_id and item.quality_level == quality_level), None)
        if not fish_item or fish_item.quantity < quantity:
            quality_label = "✨高品质" if quality_level == 1 else "普通"
            return {"success": False, "message": f"水族箱中没有足够的{quality_label}{fish_template.name}"}

        # 从水族箱移除鱼，添加到鱼塘（保持品质）
        self.inventory_repo.remove_fish_from_aquarium(user_id, fish_id, quantity, quality_level)
        self.inventory_repo.add_fish_to_inventory(user_id, fish_id, quantity, quality_level)

        quality_label = "✨高品质" if quality_level == 1 else "普通"
        return {
            "success": True, 
            "message": f"成功将 {quality_label}{fish_template.name} x{quantity} 从水族箱移回鱼塘！"
        }

    def get_aquarium_upgrades(self) -> List[AquariumUpgrade]:
        """获取所有水族箱升级配置"""
        return self.inventory_repo.get_aquarium_upgrades()

    def upgrade_aquarium(self, user_id: str) -> Dict[str, Any]:
        """升级水族箱容量"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 获取当前等级的下一个升级配置
        current_level = self._get_current_aquarium_level(user.aquarium_capacity)
        next_level = current_level + 1
        upgrade_config = self.inventory_repo.get_aquarium_upgrade_by_level(next_level)

        if not upgrade_config:
            return {"success": False, "message": "已达到最高等级"}

        # 检查用户是否有足够的金币
        if user.coins < upgrade_config.cost_coins:
            return {
                "success": False, 
                "message": f"金币不足！需要 {upgrade_config.cost_coins} 金币，当前只有 {user.coins} 金币"
            }

        # 检查用户是否有足够的钻石
        if user.premium_currency < upgrade_config.cost_premium:
            return {
                "success": False, 
                "message": f"钻石不足！需要 {upgrade_config.cost_premium} 钻石，当前只有 {user.premium_currency} 钻石"
            }

        # 扣除费用并升级
        user.coins -= upgrade_config.cost_coins
        user.premium_currency -= upgrade_config.cost_premium
        user.aquarium_capacity = upgrade_config.capacity

        try:
            self.user_repo.update(user)
            
            # 验证更新是否生效
            updated_user = self.user_repo.get_by_id(user_id)
            if updated_user and updated_user.aquarium_capacity != upgrade_config.capacity:
                return {
                    "success": False,
                    "message": f"升级失败：数据库更新异常（当前容量：{updated_user.aquarium_capacity}，期望容量：{upgrade_config.capacity}）"
                }
            
            return {
                "success": True,
                "message": f"水族箱升级成功！新容量：{upgrade_config.capacity}，花费：{upgrade_config.cost_coins} 金币"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"升级失败：{str(e)}"
            }

    def _get_current_aquarium_level(self, capacity: int) -> int:
        """根据容量获取当前等级"""
        upgrades = self.get_aquarium_upgrades()
        return next(
            (
                upgrade.level
                for upgrade in reversed(upgrades)
                if capacity >= upgrade.capacity
            ),
            1,
        )

    def get_aquarium_upgrade_info(self, user_id: str) -> Dict[str, Any]:
        """获取用户水族箱升级信息"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        current_level = self._get_current_aquarium_level(user.aquarium_capacity)
        next_level = current_level + 1
        next_upgrade = self.inventory_repo.get_aquarium_upgrade_by_level(next_level)

        upgrades = self.get_aquarium_upgrades()
        current_upgrade = self.inventory_repo.get_aquarium_upgrade_by_level(current_level)

        return {
            "success": True,
            "current_level": current_level,
            "current_capacity": user.aquarium_capacity,
            "current_upgrade": current_upgrade,
            "next_upgrade": next_upgrade,
            "all_upgrades": upgrades
        }

    def can_afford_upgrade(self, user_id: str) -> Dict[str, Any]:
        """检查用户是否可以承担升级费用"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        current_level = self._get_current_aquarium_level(user.aquarium_capacity)
        next_level = current_level + 1
        next_upgrade = self.inventory_repo.get_aquarium_upgrade_by_level(next_level)

        if not next_upgrade:
            return {"success": False, "message": "已达到最高等级"}

        can_afford_coins = user.coins >= next_upgrade.cost_coins
        can_afford_premium = user.premium_currency >= next_upgrade.cost_premium

        return {
            "success": True,
            "can_afford": can_afford_coins and can_afford_premium,
            "can_afford_coins": can_afford_coins,
            "can_afford_premium": can_afford_premium,
            "required_coins": next_upgrade.cost_coins,
            "required_premium": next_upgrade.cost_premium,
            "user_coins": user.coins,
            "user_premium": user.premium_currency
        }
