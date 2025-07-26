from datetime import datetime
from typing import Dict, Any

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractInventoryRepository,
    AbstractUserRepository,
    AbstractItemTemplateRepository
)
from ..utils import calculate_after_refine

class InventoryService:
    """封装与用户库存相关的业务逻辑"""

    def __init__(
        self,
        inventory_repo: AbstractInventoryRepository,
        user_repo: AbstractUserRepository,
        item_template_repo: AbstractItemTemplateRepository,
        config: Dict[str, Any]
    ):
        self.inventory_repo = inventory_repo
        self.user_repo = user_repo
        self.item_template_repo = item_template_repo
        self.config = config

    def get_user_fish_pond(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的鱼塘信息（鱼类库存）。
        """
        inventory_items = self.inventory_repo.get_fish_inventory(user_id)
        total_value = self.inventory_repo.get_fish_inventory_value(user_id)

        # 为了丰富信息，可以从模板仓储获取鱼的详细信息
        enriched_items = []
        for item in inventory_items:
            fish_template = self.item_template_repo.get_fish_by_id(item.fish_id)
            if fish_template:
                enriched_items.append({
                    "name": fish_template.name,
                    "rarity": fish_template.rarity,
                    "base_value": fish_template.base_value,
                    "quantity": item.quantity
                })

        return {
            "success": True,
            "fishes": enriched_items,
            "stats": {
                "total_count": sum(item["quantity"] for item in enriched_items),
                "total_value": total_value
            }
        }

    def get_user_rod_inventory(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的鱼竿库存。
        """
        rod_instances = self.inventory_repo.get_user_rod_instances(user_id)
        enriched_rods = []

        for rod_instance in rod_instances:
            rod_template = self.item_template_repo.get_rod_by_id(rod_instance.rod_id)
            if rod_template:
                enriched_rods.append({
                    "name": rod_template.name,
                    "rarity": rod_template.rarity,
                    "instance_id": rod_instance.rod_instance_id,
                    "description": rod_template.description,
                    "is_equipped": rod_instance.is_equipped,
                    "bonus_fish_quality_modifier": calculate_after_refine(rod_template.bonus_fish_quality_modifier, refine_level= rod_instance.refine_level),
                    "bonus_fish_quantity_modifier": calculate_after_refine(rod_template.bonus_fish_quantity_modifier, refine_level= rod_instance.refine_level),
                    "bonus_rare_fish_chance": calculate_after_refine(rod_template.bonus_rare_fish_chance, refine_level= rod_instance.refine_level),
                    "refine_level": rod_instance.refine_level,
                })
        return {
            "success": True,
            "rods": enriched_rods
        }

    def get_user_bait_inventory(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的鱼饵库存。
        """
        bait_inventory = self.inventory_repo.get_user_bait_inventory(user_id)
        enriched_baits = []

        for bait_id, quantity in bait_inventory.items():
            bait_template = self.item_template_repo.get_bait_by_id(bait_id)
            if bait_template:
                enriched_baits.append({
                    "bait_id": bait_id,
                    "name": bait_template.name,
                    "rarity": bait_template.rarity,
                    "quantity": quantity,
                    "duration_minutes": bait_template.duration_minutes,
                    "effect_description": bait_template.effect_description
                })

        return {
            "success": True,
            "baits": enriched_baits
        }

    def get_user_accessory_inventory(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的饰品库存。
        """
        accessory_instances = self.inventory_repo.get_user_accessory_instances(user_id)
        enriched_accessories = []

        for accessory_instance in accessory_instances:
            accessory_template = self.item_template_repo.get_accessory_by_id(accessory_instance.accessory_id)
            if accessory_template:
                enriched_accessories.append({
                    "name": accessory_template.name,
                    "rarity": accessory_template.rarity,
                    "instance_id": accessory_instance.accessory_instance_id,
                    "description": accessory_template.description,
                    "is_equipped": accessory_instance.is_equipped,
                    "bonus_fish_quality_modifier": calculate_after_refine(accessory_template.bonus_fish_quality_modifier, refine_level=accessory_instance.refine_level),
                    "bonus_fish_quantity_modifier": calculate_after_refine(accessory_template.bonus_fish_quantity_modifier, refine_level=accessory_instance.refine_level),
                    "bonus_rare_fish_chance": calculate_after_refine(accessory_template.bonus_rare_fish_chance, refine_level=accessory_instance.refine_level),
                    "bonus_coin_modifier": calculate_after_refine(accessory_template.bonus_coin_modifier, refine_level=accessory_instance.refine_level),
                    "refine_level": accessory_instance.refine_level,
                })

        return {
            "success": True,
            "accessories": enriched_accessories
        }

    def sell_all_fish(self, user_id: str, keep_one: bool = False) -> Dict[str, Any]:
        """
        向系统出售鱼。

        Args:
            user_id: 用户ID
            keep_one: 是否每种鱼保留一条
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        # 获取用户的鱼库存
        fish_inventory = self.inventory_repo.get_fish_inventory(user_id)
        if not fish_inventory:
            return {"success": False, "message": "❌ 你没有可以卖出的鱼"}
        if keep_one:
            # 调用仓储方法执行“保留一条”的数据库操作
            sold_value = self.inventory_repo.sell_fish_keep_one(user_id)
        else:
            sold_value = self.inventory_repo.get_fish_inventory_value(user_id)
            self.inventory_repo.clear_fish_inventory(user_id)

        # 更新用户金币
        user.coins += sold_value
        self.user_repo.update(user)

        return {"success": True, "message": f"💰 成功卖出鱼，获得 {sold_value} 金币"}

    def sell_fish_by_rarity(self, user_id: str, rarity: int) -> Dict[str, Any]:
        """
        向系统出售指定稀有度的鱼。

        Args:
            user_id: 用户ID
            rarity: 鱼的稀有度
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 获取用户的鱼库存
        fish_inventory = self.inventory_repo.get_fish_inventory(user_id)
        total_value = 0

        for item in fish_inventory:
            fish_id = item.fish_id
            fish_info = self.item_template_repo.get_fish_by_id(fish_id)
            if fish_info and fish_info.rarity == rarity:
                # 计算鱼的总价值
                total_value += fish_info.base_value * item.quantity
                # 删除该鱼的库存记录
                self.inventory_repo.clear_fish_inventory(user_id, rarity=rarity)
        # 如果没有可卖出的鱼，返回提示
        if total_value == 0:
            return {"success": False, "message": "❌ 没有可卖出的鱼"}
        # 更新用户金币
        user.coins += total_value
        self.user_repo.update(user)

        return {"success": True, "message": f"💰 成功卖出稀有度 {rarity} 的鱼，获得 {total_value} 金币"}

    def sell_rod(self, user_id: str, rod_instance_id: int) -> Dict[str, Any]:
        """
        向系统出售指定的鱼竿。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 1. 验证鱼竿是否属于该用户
        user_rods = self.inventory_repo.get_user_rod_instances(user_id)
        rod_to_sell = next((r for r in user_rods if r.rod_instance_id == rod_instance_id), None)

        if not rod_to_sell:
            return {"success": False, "message": "鱼竿不存在或不属于你"}

        # 2. 获取鱼竿模板以计算售价
        rod_template = self.item_template_repo.get_rod_by_id(rod_to_sell.rod_id)
        if not rod_template:
             return {"success": False, "message": "找不到鱼竿的基础信息"}

        # 3. 计算售价
        sell_prices = self.config.get("sell_prices", {}).get("by_rarity", {})
        sell_price = sell_prices.get(str(rod_template.rarity), 30) # 默认价格30

        # 4. 执行操作
        # 如果卖出的是当前装备的鱼竿，需要先卸下
        if rod_to_sell.is_equipped:
            user.equipped_rod_instance_id = None

        self.inventory_repo.delete_rod_instance(rod_instance_id)
        user.coins += sell_price
        self.user_repo.update(user)

        return {"success": True, "message": f"成功出售鱼竿【{rod_template.name}】，获得 {sell_price} 金币"}

    def sell_all_rods(self, user_id: str) -> Dict[str, Any]:
        """
        向系统出售所有鱼竿。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 获取用户的鱼竿库存
        user_rods = self.inventory_repo.get_user_rod_instances(user_id)
        if not user_rods:
            return {"success": False, "message": "❌ 你没有可以卖出的鱼竿"}

        total_value = 0
        for rod_instance in user_rods:
            if rod_instance.is_equipped:
                continue
            rod_template = self.item_template_repo.get_rod_by_id(rod_instance.rod_id)
            if rod_template and rod_template.rarity < 5:
                sell_prices = self.config.get("sell_prices", {}).get("by_rarity", {})
                sell_price = sell_prices.get(str(rod_template.rarity), 30)
                total_value += sell_price
        if total_value == 0:
            return {"success": False, "message": "❌ 没有可以卖出的鱼竿"}
        # 清空鱼竿库存
        self.inventory_repo.clear_user_rod_instances(user_id)
        # 更新用户金币
        user.coins += total_value
        self.user_repo.update(user)
        return {"success": True, "message": f"💰 成功卖出所有鱼竿，获得 {total_value} 金币"}

    def sell_accessory(self, user_id: str, accessory_instance_id: int) -> Dict[str, Any]:
        """
        向系统出售指定的饰品。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 1. 验证饰品是否属于该用户
        user_accessories = self.inventory_repo.get_user_accessory_instances(user_id)
        accessory_to_sell = next((a for a in user_accessories if a.accessory_instance_id == accessory_instance_id), None)

        if not accessory_to_sell:
            return {"success": False, "message": "饰品不存在或不属于你"}

        # 2. 获取饰品模板以计算售价
        accessory_template = self.item_template_repo.get_accessory_by_id(accessory_to_sell.accessory_id)
        if not accessory_template:
            return {"success": False, "message": "找不到饰品的基础信息"}

        # 3. 计算售价
        sell_prices = self.config.get("sell_prices", {}).get("by_rarity", {})
        sell_price = sell_prices.get(str(accessory_template.rarity), 30)

        # 4. 执行操作
        # 如果卖出的是当前装备的饰品，需要先卸下
        if accessory_to_sell.is_equipped:
            user.equipped_accessory_instance_id = None
        self.inventory_repo.delete_accessory_instance(accessory_instance_id)
        user.coins += sell_price
        self.user_repo.update(user)
        return {"success": True, "message": f"成功出售饰品【{accessory_template.name}】，获得 {sell_price} 金币"}

    def sell_all_accessories(self, user_id: str) -> Dict[str, Any]:
        """
        向系统出售所有饰品。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 获取用户的饰品库存
        user_accessories = self.inventory_repo.get_user_accessory_instances(user_id)
        if not user_accessories:
            return {"success": False, "message": "❌ 你没有可以卖出的饰品"}

        total_value = 0
        for accessory_instance in user_accessories:
            if accessory_instance.is_equipped:
                continue
            accessory_template = self.item_template_repo.get_accessory_by_id(accessory_instance.accessory_id)
            if accessory_template and accessory_template.rarity < 5:
                sell_prices = self.config.get("sell_prices", {}).get("by_rarity", {})
                sell_price = sell_prices.get(str(accessory_template.rarity), 30)
                total_value += sell_price

        if total_value == 0:
            return {"success": False, "message": "❌ 没有可以卖出的饰品"}

        # 清空饰品库存
        self.inventory_repo.clear_user_accessory_instances(user_id)
        # 更新用户金币
        user.coins += total_value
        self.user_repo.update(user)

        return {"success": True, "message": f"💰 成功卖出所有饰品，获得 {total_value} 金币"}

    def equip_item(self, user_id: str, instance_id: int, item_type: str) -> Dict[str, Any]:
        """
        装备一个物品（鱼竿或饰品）。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        equip_item_name = ""
        equip_item_id = None
        # 验证物品归属
        if item_type == "rod":
            instances = self.inventory_repo.get_user_rod_instances(user_id)
            for instance in instances:
                if instance.rod_instance_id == instance_id:
                    equip_item_id = instance.rod_id
                    break
            if instance_id not in [i.rod_instance_id for i in instances]:
                return {"success": False, "message": "❌ 鱼竿不存在或不属于你"}
            user.equipped_rod_instance_id = instance_id
            equip_item_name = self.item_template_repo.get_rod_by_id(equip_item_id).name

        elif item_type == "accessory":
            instances = self.inventory_repo.get_user_accessory_instances(user_id)
            for instance in instances:
                if instance.accessory_instance_id == instance_id:
                    equip_item_id = instance.accessory_id
                    break
            if instance_id not in [i.accessory_instance_id for i in instances]:
                return {"success": False, "message": "❌ 饰品不存在或不属于你"}
            user.equipped_accessory_instance_id = instance_id
            equip_item_name = self.item_template_repo.get_accessory_by_id(equip_item_id).name
        else:
            return {"success": False, "message": "❌ 不支持的装备类型"}

        # 统一由一个仓储方法处理装备状态的事务性
        self.inventory_repo.set_equipment_status(
            user_id,
            rod_instance_id=user.equipped_rod_instance_id,
            accessory_instance_id=user.equipped_accessory_instance_id
        )
        # 更新用户表
        self.user_repo.update(user)

        return {"success": True, "message": f"💫 装备 【{equip_item_name}】 成功！"}

    def use_bait(self, user_id: str, bait_id: int) -> Dict[str, Any]:
        """
        使用一个鱼饵。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 检查是否有此鱼饵
        bait_inventory = self.inventory_repo.get_user_bait_inventory(user_id)
        if bait_inventory.get(bait_id, 0) <= 0:
            return {"success": False, "message": "你没有这个鱼饵"}

        bait_template = self.item_template_repo.get_bait_by_id(bait_id)
        if not bait_template:
            return {"success": False, "message": "鱼饵信息不存在"}

        # 更新用户当前鱼饵状态
        user.current_bait_id = bait_id
        user.bait_start_time = datetime.now()

        self.user_repo.update(user)

        return {"success": True, "message": f"💫 成功使用鱼饵【{bait_template.name}】"}

    def get_user_fish_pond_capacity(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户鱼塘容量以及当前容量。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        fish_inventory = self.inventory_repo.get_fish_inventory(user_id)
        return {
            "success": True,
            "fish_pond_capacity": user.fish_pond_capacity,
            "current_fish_count": sum(item.quantity for item in fish_inventory),
        }

    def upgrade_fish_pond(self, user_id: str) -> Dict[str, Any]:
        """
        升级鱼塘容量。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        upgrade_path = self.config.get("pond_upgrades", [])
        current_capacity = user.fish_pond_capacity

        next_upgrade = None
        for upgrade in upgrade_path:
            if upgrade["from"] == current_capacity:
                next_upgrade = upgrade
                break

        if not next_upgrade:
            return {"success": False, "message": "鱼塘容量已达到最大，无法再升级"}

        cost = next_upgrade["cost"]
        if not user.can_afford(cost):
            return {"success": False, "message": f"金币不足，升级需要 {cost} 金币"}

        # 执行升级
        user.coins -= cost
        user.fish_pond_capacity = next_upgrade["to"]
        self.user_repo.update(user)

        return {
            "success": True,
            "message": f"鱼塘升级成功！新容量为 {user.fish_pond_capacity}。",
            "new_capacity": user.fish_pond_capacity,
            "cost": cost
        }
    def refine(self, user_id, instance_id: int, item_type: str):
        """
        精炼鱼竿或饰品，提升其属性。

        Args:
            user_id: 用户ID
            instance_id: 物品实例ID
            item_type: 物品类型，"rod"或"accessory"
        """
        # 检查用户是否存在
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 精炼费用表
        refine_costs = {1: 10000, 2: 30000, 3: 50000, 4: 100000}

        # 根据物品类型设置相关配置
        if item_type not in ["rod", "accessory"]:
            return {"success": False, "message": "❌ 不支持的精炼类型"}

        config = self._get_item_config(item_type, instance_id, user_id)
        if not config["success"]:
            return config

        # 解包配置
        instance = config["instance"]
        item_name = config["item_name"]
        id_field = config["id_field"]

        # 检查精炼等级
        if instance.refine_level > 4:
            return {"success": False, "message": "已达到最高精炼等级"}

        # 获取同类型物品列表
        same_items = config["same_items"]
        if len(same_items) < 2:
            return {"success": False, "message": f"需要至少两个同类型{item_name}进行精炼"}

        # 查找合适的消耗品进行精炼
        refine_result = self._find_refinement_candidate(
            user, instance, same_items, refine_costs, id_field, item_type
        )

        if not refine_result["success"]:
            return refine_result

        return {
            "success": True,
            "message": f"成功精炼{item_name}，新精炼等级为 {instance.refine_level}。",
            "new_refine_level": instance.refine_level
        }

    def _get_item_config(self, item_type, instance_id, user_id) -> Dict[str, Any]:
        """获取物品配置信息"""
        if item_type == "rod":
            instances = self.inventory_repo.get_user_rod_instances(user_id)
            instance = next((i for i in instances if i.rod_instance_id == instance_id), None)
            if not instance:
                return {"success": False, "message": "鱼竿不存在或不属于你"}

            template = self.item_template_repo.get_rod_by_id(instance.rod_id)
            same_items = self.inventory_repo.get_same_rod_instances(user_id, instance.rod_id)

            return {
                "success": True,
                "instance": instance,
                "template": template,
                "same_items": same_items,
                "item_name": "鱼竿",
                "id_field": "rod_instance_id"
            }

        else:  # accessory
            instances = self.inventory_repo.get_user_accessory_instances(user_id)
            instance = next((i for i in instances if i.accessory_instance_id == instance_id), None)
            if not instance:
                return {"success": False, "message": "饰品不存在或不属于你"}

            template = self.item_template_repo.get_accessory_by_id(instance.accessory_id)
            same_items = self.inventory_repo.get_same_accessory_instances(user_id, instance.accessory_id)

            return {
                "success": True,
                "instance": instance,
                "template": template,
                "same_items": same_items,
                "item_name": "饰品",
                "id_field": "accessory_instance_id"
            }

    def _find_refinement_candidate(self, user, instance, same_items, refine_costs, id_field, item_type):
        """查找可用于精炼的候选物品"""
        refine_level_from = instance.refine_level
        min_cost = None

        # 遍历所有可能的消耗品
        for candidate in same_items:
            # 跳过自身
            if getattr(candidate, id_field) == getattr(instance, id_field):
                continue

            # 计算精炼后的等级上限
            new_refine_level = min(candidate.refine_level + instance.refine_level, 5)

            # 计算精炼成本
            total_cost = 0
            for level in range(refine_level_from, new_refine_level):
                total_cost += refine_costs.get(level, 0)

            # 记录最低成本
            if min_cost is None or total_cost < min_cost:
                min_cost = total_cost

            # 检查用户是否有足够的金币
            if not user.can_afford(total_cost):
                continue

            # 执行精炼操作
            self._perform_refinement(user, instance, candidate, new_refine_level, total_cost, item_type)
            return {"success": True}

        # 如果没找到合适的候选品，返回错误
        return {"success": False, "message": f"至少需要 {min_cost} 金币才能精炼，当前金币不足"}

    def _perform_refinement(self, user, instance, candidate, new_refine_level, cost, item_type):
        """执行精炼操作"""
        # 扣除金币
        user.coins -= cost

        # 提升精炼等级
        instance.refine_level = new_refine_level

        # 根据物品类型执行相应操作
        if item_type == "rod":
            self.inventory_repo.update_rod_instance(instance)
            self.inventory_repo.delete_rod_instance(candidate.rod_instance_id)
        else:  # accessory
            self.inventory_repo.update_accessory_instance(instance)
            self.inventory_repo.delete_accessory_instance(candidate.accessory_instance_id)

        # 更新用户信息
        self.user_repo.update(user)