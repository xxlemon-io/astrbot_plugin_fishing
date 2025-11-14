from typing import Dict, Any, List, Optional
from ..repositories.abstract_repository import AbstractItemTemplateRepository, AbstractGachaRepository
from ..domain.models import Fish, Rod, Bait, Accessory, GachaPool, Item, Title


class ItemTemplateService:
    """封装所有游戏模板数据的后台管理业务逻辑"""

    def __init__(
            self,
            item_template_repo: AbstractItemTemplateRepository,
            gacha_repo: AbstractGachaRepository
    ):
        self.item_template_repo = item_template_repo
        self.gacha_repo = gacha_repo

    # --- Fish Methods ---
    def get_fish_by_id(self, fish_id: int) -> Optional[Fish]:
        return self.item_template_repo.get_fish_by_id(fish_id)

    def get_all_fish(self) -> List[Fish]:
        return self.item_template_repo.get_all_fish()

    def add_fish_template(self, data: Dict[str, Any]):
        # 服务层可以添加数据验证逻辑，支持任意稀有度级别
        self.item_template_repo.add_fish_template(data)

    def update_fish_template(self, fish_id: int, data: Dict[str, Any]):
        self.item_template_repo.update_fish_template(fish_id, data)

    def delete_fish_template(self, fish_id: int):
        self.item_template_repo.delete_fish_template(fish_id)

    # --- Rod Methods ---
    def get_rod_by_id(self, rod_id: int) -> Optional[Rod]:
        return self.item_template_repo.get_rod_by_id(rod_id)

    def get_all_rods(self) -> List[Rod]:
        return self.item_template_repo.get_all_rods()

    def add_rod_template(self, data: Dict[str, Any]):
        self.item_template_repo.add_rod_template(data)

    def update_rod_template(self, rod_id: int, data: Dict[str, Any]):
        self.item_template_repo.update_rod_template(rod_id, data)

    def delete_rod_template(self, rod_id: int):
        self.item_template_repo.delete_rod_template(rod_id)

    # --- Bait Methods ---
    def get_bait_by_id(self, bait_id: int) -> Optional[Bait]:
        return self.item_template_repo.get_bait_by_id(bait_id)

    def get_all_baits(self) -> List[Bait]:
        return self.item_template_repo.get_all_baits()

    def add_bait_template(self, data: Dict[str, Any]):
        self.item_template_repo.add_bait_template(data)

    def update_bait_template(self, bait_id: int, data: Dict[str, Any]):
        self.item_template_repo.update_bait_template(bait_id, data)

    def delete_bait_template(self, bait_id: int):
        self.item_template_repo.delete_bait_template(bait_id)

    # --- Accessory Methods ---
    def get_accessory_by_id(self, accessory_id: int) -> Optional[Accessory]:
        return self.item_template_repo.get_accessory_by_id(accessory_id)

    def get_all_accessories(self) -> List[Accessory]:
        return self.item_template_repo.get_all_accessories()

    def add_accessory_template(self, data: Dict[str, Any]):
        self.item_template_repo.add_accessory_template(data)

    def update_accessory_template(self, accessory_id: int, data: Dict[str, Any]):
        self.item_template_repo.update_accessory_template(accessory_id, data)

    def delete_accessory_template(self, accessory_id: int):
        self.item_template_repo.delete_accessory_template(accessory_id)

    # --- Item Methods ---
    def get_item_by_id(self, item_id: int) -> Optional[Item]:
        return self.item_template_repo.get_item_by_id(item_id)

    def get_all_items(self) -> List[Item]:
        return self.item_template_repo.get_all_items()

    def add_item_template(self, data: Dict[str, Any]):
        self.item_template_repo.add_item_template(data)

    def update_item_template(self, item_id: int, data: Dict[str, Any]):
        self.item_template_repo.update_item_template(item_id, data)

    def delete_item_template(self, item_id: int):
        self.item_template_repo.delete_item_template(item_id)

    # --- Title Methods ---
    def get_title_by_id(self, title_id: int) -> Optional[Title]:
        return self.item_template_repo.get_title_by_id(title_id)

    def get_title_by_name(self, name: str) -> Optional[Title]:
        return self.item_template_repo.get_title_by_name(name)

    def update_title_template(self, title_id: int, data: Dict[str, Any]):
        self.item_template_repo.update_title_template(title_id, data)

    def delete_title_template(self, title_id: int):
        self.item_template_repo.delete_title_template(title_id)

    # --- Gacha Pool Methods ---
    def get_all_gacha_pools(self) -> List[GachaPool]:
        return self.gacha_repo.get_all_pools()

    def add_pool_template(self, data: Dict[str, Any]):
        # 服务层可以包含验证逻辑，例如检查名称是否重复等
        self.gacha_repo.add_pool_template(data)

    def update_pool_template(self, pool_id: int, data: Dict[str, Any]):
        self.gacha_repo.update_pool_template(pool_id, data)

    def delete_pool_template(self, pool_id: int):
        self.gacha_repo.delete_pool_template(pool_id)

    def copy_pool_template(self, pool_id: int) -> int:
        """复制一个抽卡池及其所有物品"""
        return self.gacha_repo.copy_pool_template(pool_id)

    def get_pool_details_for_admin(self, pool_id: int) -> Dict[str, Any]:
        pool = self.gacha_repo.get_pool_by_id(pool_id)
        # 为后台提供所有可添加的物品选项
        all_rods = self.item_template_repo.get_all_rods()
        all_baits = self.item_template_repo.get_all_baits()
        all_accessories = self.item_template_repo.get_all_accessories()
        return {
            "pool": pool,
            "all_rods": all_rods,
            "all_baits": all_baits,
            "all_accessories": all_accessories
        }

    # --- Gacha Pool Item Methods ---
    def add_item_to_pool(self, pool_id: int, data: Dict[str, Any]):
        self.gacha_repo.add_item_to_pool(pool_id, data)

    def update_pool_item(self, item_pool_id: int, data: Dict[str, Any]):
        self.gacha_repo.update_pool_item(item_pool_id, data)

    def delete_pool_item(self, item_pool_id: int):
        self.gacha_repo.delete_pool_item(item_pool_id)
