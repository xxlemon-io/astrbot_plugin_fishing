from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

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
class Item:
    """代表一道具的模板信息（背包道具栏）"""
    item_id: int
    name: str
    rarity: int
    description: Optional[str] = None
    effect_description: Optional[str] = None
    item_type: str = "consumable"  # consumable, tool, key 等
    cost: int = 0
    is_consumable: bool = True
    icon_url: Optional[str] = None
    effect_type: Optional[str] = None
    effect_payload: Optional[str] = None

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
    # 限时开放控制
    is_limited_time: int = 0  # 0/1 存储于数据库，前端按布尔使用
    open_until: Optional[str] = None  # 以文本存储的ISO时间（SQLite）
    # 这个字段让模型更丰富，可以在服务层组装，存放该池的所有奖品
    items: List[GachaPoolItem] = field(default_factory=list)

    def __getitem__(self, item):
        """允许通过属性名访问字段"""
        return getattr(self, item)

@dataclass
class Commodity:
    """代表一种大宗商品的模板信息"""
    commodity_id: str  # e.g., 'dried_fish', 'fish_roe', 'fish_oil'
    name: str
    description: str


# ---------------------------------
# 交易所实体 (Exchange Entities)
# ---------------------------------

@dataclass
class Exchange:
    """代表交易所的商品价格记录"""
    date: str  # YYYY-MM-DD
    time: str  # HH:MM:SS
    commodity_id: str
    price: int
    update_type: str = "auto"  # 'auto' 或 'manual'
    created_at: str = ""  # ISO格式时间戳

@dataclass
class UserCommodity:
    """代表用户持有的一个具体的大宗商品实例"""
    instance_id: int
    user_id: str
    commodity_id: str
    quantity: int
    purchase_price: int
    purchased_at: datetime
    expires_at: datetime

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
    is_locked: bool = False  # 是否锁定保护，默认为False

@dataclass
class UserAccessoryInstance:
    """代表用户拥有的一个具体的饰品实例"""
    accessory_instance_id: int
    user_id: str
    accessory_id: int
    is_equipped: bool
    obtained_at: datetime
    refine_level: int = 1
    is_locked: bool = False  # 是否锁定保护，默认为False

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
    max_coins: int = 0  # 历史最高金币数
    consecutive_login_days: int = 0
    fish_pond_capacity: int = 480
    aquarium_capacity: int = 50  # 水族箱容量
    fishing_zone_id: int = 1  # 默认钓鱼区域ID
    exchange_account_status: bool = False # 交易所账户状态

    max_wipe_bomb_multiplier: float = 0.0
    min_wipe_bomb_multiplier: Optional[float] = None

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
    last_electric_fish_time: Optional[datetime] = None
    last_login_time: Optional[datetime] = None
    last_stolen_at: Optional[datetime] = None
    wipe_bomb_forecast: Optional[str] = None  # 'good' or 'bad'

    # --- 新增：用于“命运之轮”游戏的状态字段 ---
    in_wheel_of_fate: bool = False
    wof_current_level: int = 0
    wof_current_prize: int = 0
    wof_entry_fee: int = 0
    last_wof_play_time: datetime | None = None
    wof_last_action_time: datetime | None = None
    wof_plays_today: int = 0
    last_wof_date: Optional[str] = None # YYYY-MM-DD 格式
    
    # --- 新增：用于“骰宝”游戏冷却 ---
    last_sicbo_time: Optional[datetime] = None
    
    # --- 新增：用于每日擦弹次数追踪 ---
    wipe_bomb_attempts_today: int = 0
    last_wipe_bomb_date: Optional[str] = None # YYYY-MM-DD 格式

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
    quality_level: int  # 0=普通，1=高品质
    quantity: int

@dataclass
class UserAquariumItem:
    """用户水族箱中的一项"""
    user_id: str
    fish_id: int
    quality_level: int  # 0=普通，1=高品质
    quantity: int
    added_at: Optional[datetime] = None

@dataclass
class AquariumUpgrade:
    """水族箱升级配置"""
    upgrade_id: int
    level: int
    capacity: int
    cost_coins: int
    cost_premium: int = 0
    description: Optional[str] = None
    created_at: Optional[datetime] = None

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
    item_description: Optional[str]
    quantity: int
    price: int
    listed_at: datetime
    item_instance_id: Optional[int] = None  # 实例ID，用于显示短码
    refine_level: int = 1
    quality_level: int = 0  # 品质等级（仅对鱼类有效，0=普通，1=高品质）
    expires_at: Optional[datetime] = None  # 腐败日期，主要用于大宗商品
    is_anonymous: bool = False  # 是否为匿名上架

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
    # 当天稀有鱼（4星及以上）的配额
    daily_rare_fish_quota: int
    # 今天已被钓走的稀有鱼数量
    rare_fish_caught_today: int = 0
    # 区域的特定配置
    configs: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    specific_fish_ids: List[int] = field(default_factory=list)
    # 通行证要求相关字段
    required_item_id: Optional[int] = None  # 需要的通行证道具ID
    requires_pass: bool = False  # 是否需要通行证
    # 钓鱼消耗相关字段
    fishing_cost: int = 10  # 在该区域钓鱼消耗的金币

    def __post_init__(self):
        if isinstance(self.is_active, int):
            self.is_active = bool(self.is_active)

    def __getitem__(self, item):
        """允许通过属性名访问字段"""
        return getattr(self, item)

@dataclass
class UserBuff:
    id: int
    user_id: str
    buff_type: str
    payload: Optional[str]
    started_at: datetime
    expires_at: Optional[datetime]


@dataclass
class UserItem:
    user_id: str

@dataclass
class UserFishStat:
    """用户对某鱼种的聚合统计，用于图鉴与个人纪录"""
    user_id: str
    fish_id: int
    first_caught_at: Optional[datetime]
    last_caught_at: Optional[datetime]
    max_weight: int
    min_weight: int
    total_caught: int
    total_weight: int

# ---------------------------------
# 商店实体 (Shop Entities) - 新设计
# ---------------------------------

@dataclass
class Shop:
    """商店实体"""
    shop_id: int
    name: str
    description: Optional[str] = None
    shop_type: str = "normal"  # 'normal' | 'premium' | 'limited'
    is_active: bool = True
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    daily_start_time: Optional[str] = None  # 格式: "09:00"
    daily_end_time: Optional[str] = None    # 格式: "18:00"
    sort_order: int = 100
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ShopItem:
    """商店商品实体"""
    item_id: int
    shop_id: int
    name: str
    description: Optional[str] = None
    category: str = "general"
    stock_total: Optional[int] = None
    stock_sold: int = 0
    per_user_limit: Optional[int] = None
    per_user_daily_limit: Optional[int] = None
    is_active: bool = True
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    sort_order: int = 100
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ShopItemCost:
    """商店商品成本实体（支持AND/OR关系）"""
    cost_id: int
    item_id: int
    cost_type: str  # 'coins' | 'premium' | 'item' | 'fish' | 'rod' | 'accessory'
    cost_amount: int
    cost_item_id: Optional[int] = None
    cost_relation: str = "and"  # 'and' | 'or'
    group_id: Optional[int] = None
    quality_level: int = 0  # 品质等级（仅对鱼类有效，0=普通，1=高品质）


@dataclass
class ShopItemReward:
    """商店商品奖励实体"""
    reward_id: int
    item_id: int
    reward_type: str  # 'rod' | 'accessory' | 'bait' | 'item' | 'fish' | 'coins'
    reward_item_id: Optional[int] = None
    reward_quantity: int = 1
    reward_refine_level: Optional[int] = None
    quality_level: int = 0  # 品质等级（仅对鱼类有效，0=普通，1=高品质）


@dataclass
class ShopPurchaseRecord:
    """商店购买记录实体"""
    record_id: int
    user_id: str
    item_id: int  # 现在引用 shop_items.item_id
    quantity: int
    timestamp: datetime


# ---------------------------------
# 兼容性模型（向后兼容旧系统）
# ---------------------------------

@dataclass
class ShopOfferCost:
    """商店消耗项（兼容旧接口）"""
    cost_id: int
    offer_id: int
    cost_type: str  # 'coins' | 'premium' | 'item' | 'fish'
    amount: int
    item_id: Optional[int] = None


@dataclass
class ShopOffer:
    """商店在售条目（兼容旧接口）"""
    offer_id: int
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    per_user_limit: Optional[int] = None
    per_user_daily_limit: Optional[int] = None
    stock_total: Optional[int] = None
    stock_sold: int = 0
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ShopOfferReward:
    """商店奖励项（兼容旧接口）"""
    reward_id: int
    offer_id: int
    item_type: str
    item_id: int
    quantity: int
    refine_level: Optional[int] = None


# ---------------------------------
# 红包系统实体 (Red Packet Entities)
# ---------------------------------

@dataclass
class RedPacket:
    """红包实体"""
    packet_id: int
    sender_id: str
    group_id: str
    packet_type: str  # 'normal' 普通红包, 'lucky' 拼手气红包, 'password' 口令红包
    total_amount: int
    total_count: int
    remaining_amount: int
    remaining_count: int
    password: Optional[str] = None  # 口令红包的口令
    created_at: datetime = None
    expires_at: datetime = None
    is_expired: bool = False

@dataclass
class RedPacketRecord:
    """红包领取记录"""
    record_id: int
    packet_id: int
    user_id: str
    amount: int
    claimed_at: datetime = None
