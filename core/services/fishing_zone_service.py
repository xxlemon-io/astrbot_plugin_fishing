import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime

from ..domain.models import User, FishingZone
from ..repositories.abstract_repository import AbstractItemTemplateRepository, AbstractInventoryRepository


class FishingZoneStrategy(ABC):
    """钓鱼区域策略的抽象基类"""

    def __init__(self, item_template_repo: AbstractItemTemplateRepository, config: Dict[str, Any],
                 zone_config: Dict[str, Any]):
        self.item_template_repo = item_template_repo
        self.config = config
        self.zone_config = zone_config

    @abstractmethod
    def get_fish_rarity_distribution(self, user: User) -> List[float]:
        """根据用户和区域配置计算鱼的稀有度分布"""
        pass


class Zone1Strategy(FishingZoneStrategy):
    """区域一：新手港湾"""

    def get_fish_rarity_distribution(self, user: User) -> List[float]:
        # 新手区域逻辑：只能钓到1-4星鱼，4星鱼概率很低，无6+星
        # 分布格式：[1星, 2星, 3星, 4星, 5星, 6+星]
        rarity_dist = self.zone_config.get("rarity_distribution")
        if rarity_dist is None or not rarity_dist:
            # 默认分布：主要1-4星，少量5星，无6+星
            return [0.6, 0.3, 0.08, 0.02, 0, 0]  # 6个元素：1-5星 + 6+星
        # 确保返回的分布数组长度为6
        while len(rarity_dist) < 6:
            rarity_dist.append(0.0)
        return rarity_dist[:6]  # 截取到6个元素


class Zone2Strategy(FishingZoneStrategy):
    """区域二：深海峡谷"""

    def get_fish_rarity_distribution(self, user: User) -> List[float]:
        # 深海峡谷逻辑：4星鱼概率提升，有极小概率钓到5星鱼
        # 分布格式：[1星, 2星, 3星, 4星, 5星, 6+星]
        rarity_dist = self.zone_config.get("rarity_distribution")
        if rarity_dist is None or not rarity_dist:
            # 默认分布：重点4-5星，少量6+星
            return [0.4, 0.3, 0.2, 0.09, 0.01, 0]  # 6个元素：1-5星 + 6+星
        # 确保返回的分布数组长度为6
        while len(rarity_dist) < 6:
            rarity_dist.append(0.0)
        return rarity_dist[:6]  # 截取到6个元素


class Zone3Strategy(FishingZoneStrategy):
    """区域三：传说之海"""

    def get_fish_rarity_distribution(self, user: User) -> List[float]:
        # 传说之海逻辑：5星鱼概率大幅提升，少量6+星
        # 分布格式：[1星, 2星, 3星, 4星, 5星, 6+星]
        rarity_dist = self.zone_config.get("rarity_distribution")
        if rarity_dist is None or not rarity_dist:
            # 默认分布：重点5星，少量6+星
            return [0.3, 0.2, 0.2, 0.2, 0.08, 0.02]  # 6个元素：1-5星 + 6+星
        # 确保返回的分布数组长度为6
        while len(rarity_dist) < 6:
            rarity_dist.append(0.0)
        return rarity_dist[:6]  # 截取到6个元素


class CustomZoneStrategy(FishingZoneStrategy):
    """自定义区域策略"""

    def get_fish_rarity_distribution(self, user: User) -> List[float]:
        # 自定义区域完全依赖配置中的稀有度分布
        # 分布格式：[1星, 2星, 3星, 4星, 5星, 6+星]
        rarity_dist = self.zone_config.get("rarity_distribution")
        if rarity_dist is None or not rarity_dist:
            # 默认均匀分布：1-5星和6+星均等概率
            return [0.16, 0.16, 0.16, 0.16, 0.16, 0.2]  # 6个元素：1-5星 + 6+星
        # 确保返回的分布数组长度为6
        while len(rarity_dist) < 6:
            rarity_dist.append(0.0)
        return rarity_dist[:6]  # 截取到6个元素


class FishingZoneService:
    def __init__(self, item_template_repo: AbstractItemTemplateRepository,
                 inventory_repo: AbstractInventoryRepository,
                 config: Dict[str, Any]):
        self.item_template_repo = item_template_repo
        self.inventory_repo = inventory_repo
        self.config = config
        self.strategies = self._load_strategies()

    def _load_strategies(self) -> Dict[int, FishingZoneStrategy]:
        zones = self.inventory_repo.get_all_zones()
        strategies = {}
        for zone in zones:
            if not zone.is_active:
                continue

            from ..utils import get_now
            now = get_now()
            if zone.available_from and now < zone.available_from:
                continue
            if zone.available_until and now > zone.available_until:
                continue
            
            zone.specific_fish_ids = self.inventory_repo.get_specific_fish_ids_for_zone(zone.id)
            
            zone_config = zone.configs if zone.configs else {}
            if zone.id == 1:
                strategies[zone.id] = Zone1Strategy(self.item_template_repo, self.config, zone_config)
            elif zone.id == 2:
                strategies[zone.id] = Zone2Strategy(self.item_template_repo, self.config, zone_config)
            elif zone.id == 3:
                strategies[zone.id] = Zone3Strategy(self.item_template_repo, self.config, zone_config)
            else:
                # 对于自定义区域（ID > 3），使用专门的自定义策略
                strategies[zone.id] = CustomZoneStrategy(self.item_template_repo, self.config, zone_config)
        return strategies

    def get_strategy(self, zone_id: int) -> FishingZoneStrategy:
        strategy = self.strategies.get(zone_id)
        if not strategy:
            # 默认返回区域1的策略
            return self.strategies.get(1)
        return strategy

    def get_all_zones(self) -> List[Dict[str, Any]]:
        zones = self.inventory_repo.get_all_zones()
        zones_data = []
        for zone in zones:
            specific_fish_ids = self.inventory_repo.get_specific_fish_ids_for_zone(zone.id)
            zones_data.append({
                "id": zone.id,
                "name": zone.name,
                "description": zone.description,
                "daily_rare_fish_quota": zone.daily_rare_fish_quota,
                "configs": zone.configs,
                "is_active": zone.is_active,
                "available_from": zone.available_from.isoformat() if zone.available_from else None,
                "available_until": zone.available_until.isoformat() if zone.available_until else None,
                "specific_fish_ids": specific_fish_ids,
                "required_item_id": zone.required_item_id,
                "requires_pass": zone.requires_pass,
                "fishing_cost": zone.fishing_cost
            })
        return zones_data

    def create_zone(self, zone_data: Dict[str, Any]) -> Dict[str, Any]:
        new_zone = self.inventory_repo.create_zone(zone_data)
        self.strategies = self._load_strategies()  # Reload strategies
        return {"id": new_zone.id, "name": new_zone.name}

    def update_zone(self, zone_id: int, zone_data: Dict[str, Any]):
        self.inventory_repo.update_zone(zone_id, zone_data)
        if 'specific_fish_ids' in zone_data:
            self.inventory_repo.update_specific_fish_for_zone(zone_id, zone_data['specific_fish_ids'])
        self.strategies = self._load_strategies()  # Reload strategies

    def delete_zone(self, zone_id: int):
        self.inventory_repo.delete_zone(zone_id)
        self.strategies = self._load_strategies()  # Reload strategies
