from typing import Dict, Any

# 导入仓储接口
from ..repositories.abstract_repository import (
    AbstractItemTemplateRepository,
    AbstractInventoryRepository,
    AbstractUserRepository
)

class ShopService:
    """封装与系统商店相关的业务逻辑"""

    def __init__(
        self,
        item_template_repo: AbstractItemTemplateRepository,
        inventory_repo: AbstractInventoryRepository,
        user_repo: AbstractUserRepository
    ):
        self.item_template_repo = item_template_repo
        self.inventory_repo = inventory_repo
        self.user_repo = user_repo

    def get_shop_listings(self) -> Dict[str, Any]:
        """
        获取商店中所有可供出售的商品列表。
        """
        all_rods = self.item_template_repo.get_all_rods()
        all_baits = self.item_template_repo.get_all_baits()
        # 未来可以轻松扩展到饰品等其他物品
        # all_accessories = self.item_template_repo.get_all_accessories()

        shop_rods = [
            rod for rod in all_rods
            if rod.source == "shop" and rod.purchase_cost is not None and rod.purchase_cost > 0
        ]
        shop_baits = [
            bait for bait in all_baits
            if bait.cost is not None and bait.cost > 0
        ]

        return {
            "success": True,
            "rods": shop_rods,
            "baits": shop_baits
        }

    def buy_item(self, user_id: str, item_type: str, item_template_id: int, quantity: int = 1) -> Dict[str, Any]:
        """
        处理玩家从商店购买物品的逻辑。

        Args:
            user_id: 购买者ID
            item_type: 物品类型 ('rod', 'bait', etc.)
            item_template_id: 物品模板ID
            quantity: 购买数量

        Returns:
            一个包含成功状态和消息的字典。
        """
        if quantity <= 0:
            return {"success": False, "message": "购买数量必须大于0"}

        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        total_cost = 0
        item_name = "未知物品"
        item_template = None

        # 1. 获取物品信息并计算总价
        if item_type == "rod":
            if quantity > 1:
                return {"success": False, "message": "鱼竿一次只能购买一个"}
            item_template = self.item_template_repo.get_rod_by_id(item_template_id)
            if item_template and item_template.source == "shop" and item_template.purchase_cost:
                total_cost = item_template.purchase_cost
                item_name = item_template.name
            else:
                return {"success": False, "message": "此鱼竿无法购买"}

        elif item_type == "bait":
            item_template = self.item_template_repo.get_bait_by_id(item_template_id)
            if item_template and item_template.cost:
                total_cost = item_template.cost * quantity
                item_name = item_template.name
            else:
                return {"success": False, "message": "此鱼饵无法购买"}

        else:
            return {"success": False, "message": "不支持购买的物品类型"}

        # 2. 检查金币是否足够
        if not user.can_afford(total_cost):
            return {"success": False, "message": f"金币不足，需要 {total_cost} 金币"}

        # 3. 执行交易：扣款并发货
        user.coins -= total_cost
        self.user_repo.update(user)

        if item_type == "rod" and item_template:
            self.inventory_repo.add_rod_instance(
                user_id=user_id,
                rod_id=item_template.rod_id,
                durability=item_template.durability
            )
        elif item_type == "bait":
            self.inventory_repo.update_bait_quantity(
                user_id=user_id,
                bait_id=item_template_id,
                delta=quantity
            )

        return {"success": True, "message": f"✅ 成功购买 {item_name} x{quantity}，花费 {total_cost} 金币"}
