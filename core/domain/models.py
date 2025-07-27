from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

# ---------------------------------
# 游戏配置实体 (Configuration Entities)
# ---------------------------------

@dataclass
class Fish:
    """代表一种鱼的模板信息"""
    fish_id: int
    name: str
    rarity: int
    base_value: int
    min_weight: int
    max_weight: int
    description: Optional[str] = None
    icon_url: Optional[str] = None

@dataclass
class Bait:
    """代表一种鱼饵的模板信息"""
    bait_id: int
    name: str
    rarity: int
    description: Optional[str] = None
    effect_description: Optional[str] = None  # 保留此字段用于向玩家展示

    # 新增的结构化效果字段
    duration_minutes: int = 0
    cost: int = 0
    required_rod_rarity: int = 0
    success_rate_modifier: float = 0.0 # 成功率加成
    rare_chance_modifier: float = 0.0 # 稀有鱼出现几率加成
    garbage_reduction_modifier: float = 0.0 # 垃圾鱼出现几率减少
    value_modifier: float = 1.0 # 渔获价值加成
    quantity_modifier: float = 1.0 # 渔获数量加成
    is_consumable: bool = True # 是否消耗品


@dataclass
class Rod:
    """代表一种鱼竿的模板信息"""
    rod_id: int
    name: str
    rarity: int
    source: str  # 'shop', 'gacha', 'event'
    description: Optional[str] = None
    purchase_cost: Optional[int] = None
    bonus_fish_quality_modifier: float = 1.0
    bonus_fish_quantity_modifier: float = 1.0
    bonus_rare_fish_chance: float = 0.0
    durability: Optional[int] = None
    icon_url: Optional[str] = None

@dataclass
class Accessory:
    """代表一种饰品的模板信息"""
    accessory_id: int
    name: str
    rarity: int
    slot_type: str = "general"
    description: Optional[str] = None
    bonus_fish_quality_modifier: float = 1.0
    bonus_fish_quantity_modifier: float = 1.0
    bonus_rare_fish_chance: float = 0.0
    bonus_coin_modifier: float = 1.0
    other_bonus_description: Optional[str] = None
    icon_url: Optional[str] = None

@dataclass
class Title:
    """代表一种称号的模板信息"""
    title_id: int
    name: str
    description: str
    display_format: str = "{name}"

@dataclass
class Achievement:
    """代表一个成就的模板信息"""
    achievement_id: int
    name: str
    description: str
    target_type: str
    target_value: int
    reward_type: str
    target_fish_id: Optional[int] = None
    reward_value: Optional[int] = None
    reward_quantity: int = 1
    is_repeatable: bool = False
    icon_url: Optional[str] = None

@dataclass
class GachaPoolItem:
    """代表抽卡池中的一个奖品项"""
    gacha_pool_item_id: int
    gacha_pool_id: int
    item_type: str
    item_id: int
    weight: int
    quantity: int = 1

@dataclass
class GachaPool:
    """代表一个抽卡池的配置"""
    gacha_pool_id: int
    name: str
    description: Optional[str] = None
    cost_coins: int = 0
    cost_premium_currency: int = 0
    # 这个字段让模型更丰富，可以在服务层组装，存放该池的所有奖品
    items: List[GachaPoolItem] = field(default_factory=list)

    def __getitem__(self, item):
        """允许通过属性名访问字段"""
        return getattr(self, item)

# ---------------------------------
# 用户数据实体 (User Data Entities)
# ---------------------------------

@dataclass
class UserRodInstance:
    """代表用户拥有的一个具体的鱼竿实例"""
    rod_instance_id: int
    user_id: str
    rod_id: int
    is_equipped: bool
    obtained_at: datetime
    refine_level: int = 1  # 精炼等级，默认为1
    current_durability: Optional[int] = None

@dataclass
class UserAccessoryInstance:
    """代表用户拥有的一个具体的饰品实例"""
    accessory_instance_id: int
    user_id: str
    accessory_id: int
    is_equipped: bool
    obtained_at: datetime
    refine_level: int = 1

@dataclass
class User:
    """代表一个完整的用户领域模型"""
    # --- 无默认值的字段放前面 ---
    user_id: str
    created_at: datetime
    nickname: Optional[str]

    # --- 有默认值的字段放后面 ---
    coins: int = 0
    premium_currency: int = 0
    total_fishing_count: int = 0
    total_weight_caught: int = 0
    total_coins_earned: int = 0
    consecutive_login_days: int = 0
    fish_pond_capacity: int = 480
    fishing_zone_id: int = 1  # 默认钓鱼区域ID

    # 装备信息
    equipped_rod_instance_id: Optional[int] = None
    equipped_accessory_instance_id: Optional[int] = None
    current_title_id: Optional[int] = None
    current_bait_id: Optional[int] = None
    bait_start_time: Optional[datetime] = None

    # 状态信息
    auto_fishing_enabled: bool = False
    last_fishing_time: Optional[datetime] = None
    last_wipe_bomb_time: Optional[datetime] = None
    last_steal_time: Optional[datetime] = None
    last_login_time: Optional[datetime] = None
    last_stolen_at: Optional[datetime] = None

    def can_afford(self, cost: int) -> bool:
        """判断用户金币是否足够"""
        return self.coins >= cost

# ---------------------------------
# 关联与日志实体 (Association & Log Entities)
# ---------------------------------

@dataclass
class UserFishInventoryItem:
    """用户鱼塘中的一项"""
    user_id: str
    fish_id: int
    quantity: int

@dataclass
class FishingRecord:
    """一条详细的钓鱼记录"""
    record_id: int
    user_id: str
    fish_id: int
    weight: int
    value: int
    timestamp: datetime
    rod_instance_id: Optional[int] = None
    accessory_instance_id: Optional[int] = None
    bait_id: Optional[int] = None
    location_id: Optional[int] = None
    is_king_size: bool = False

@dataclass
class GachaRecord:
    """一条抽卡记录"""
    record_id: int
    user_id: str
    gacha_pool_id: int
    item_type: str
    item_id: int
    item_name: str
    timestamp: datetime
    quantity: int = 1
    rarity: int = 1

    def __getitem__(self, item):
        """允许通过属性名访问字段"""
        return getattr(self, item)

@dataclass
class WipeBombLog:
    """一条擦弹记录"""
    log_id: int
    user_id: str
    contribution_amount: int
    reward_multiplier: float
    reward_amount: int
    timestamp: datetime

@dataclass
class MarketListing:
    """一个市场商品条目"""
    market_id: int
    user_id: str
    seller_nickname: str
    item_type: str
    item_id: int
    item_name: str
    item_description: str
    quantity: int
    price: int
    listed_at: datetime
    refine_level: int = 1
    expires_at: Optional[datetime] = None

    def __getitem__(self, item):
        """允许通过属性名访问字段"""
        return getattr(self, item)

@dataclass
class TaxRecord:
    """一条税收记录"""
    tax_id: int
    user_id: str
    tax_amount: int
    tax_rate: float
    original_amount: int
    balance_after: int
    timestamp: datetime
    tax_type: str = "daily"

@dataclass
class FishingZone:
    id: int
    name: str
    description: str
    # 当天稀有鱼（4星和5星）的配额
    daily_rare_fish_quota: int
    # 今天已被钓走的稀有鱼数量
    rare_fish_caught_today: int = 0

    def __getitem__(self, item):
        """允许通过属性名访问字段"""
        return getattr(self, item)
