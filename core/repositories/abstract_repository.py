from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import date, datetime

# 从领域模型导入所有需要的实体
from ..domain.models import (
    User, Fish, Rod, Bait, Accessory, Title, Achievement,
    UserRodInstance, UserAccessoryInstance, UserFishInventoryItem,
    FishingRecord, GachaRecord, WipeBombLog, MarketListing, TaxRecord,
    GachaPool, GachaPoolItem, FishingZone
)

# 定义用户成就进度的数据结构
UserAchievementProgress = Dict[int, Dict[str, Any]] # {achievement_id: {progress: X, completed_at: Y}}

class AbstractUserRepository(ABC):
    """用户数据仓储接口"""
    # 根据ID获取用户
    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[User]: pass
    # 检查用户是否存在
    @abstractmethod
    def check_exists(self, user_id: str) -> bool: pass
    # 新增一个用户
    @abstractmethod
    def add(self, user: User) -> None: pass
    # 更新用户信息
    @abstractmethod
    def update(self, user: User) -> None: pass
    # 获取所有用户ID
    @abstractmethod
    def get_all_user_ids(self, auto_fishing_only: bool = False) -> List[str]: pass
    # 获取排行榜所需的核心数据
    @abstractmethod
    def get_leaderboard_data(self, limit: int) -> List[Dict[str, Any]]: pass
    # 获取资产超过阈值的用户列表
    @abstractmethod
    def get_high_value_users(self, threshold: int) -> List[User]: pass
    # 获取所有用户（分页）
    @abstractmethod
    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[User]: pass
    # 获取用户总数
    @abstractmethod
    def get_users_count(self) -> int: pass
    # 搜索用户（支持分页）
    @abstractmethod
    def search_users(self, keyword: str, limit: int = 50, offset: int = 0) -> List[User]: pass
    # 搜索用户的总数
    @abstractmethod
    def get_search_users_count(self, keyword: str) -> int: pass
    # 删除用户
    @abstractmethod
    def delete_user(self, user_id: str) -> bool: pass

class AbstractItemTemplateRepository(ABC):
    """物品模板数据仓储接口"""
    # 获取鱼类模板
    @abstractmethod
    def get_fish_by_id(self, fish_id: int) -> Optional[Fish]: pass
    # 获取所有鱼类模板
    @abstractmethod
    def get_all_fish(self) -> List[Fish]: pass
    # 根据稀有度获取鱼类模板
    @abstractmethod
    def get_fishes_by_rarity(self, rarity: int) -> List[Fish]: pass
    # 获取鱼竿模板
    @abstractmethod
    def get_rod_by_id(self, rod_id: int) -> Optional[Rod]: pass
    # 获取所有鱼竿模板
    @abstractmethod
    def get_all_rods(self) -> List[Rod]: pass
    # 获取鱼饵模板
    @abstractmethod
    def get_bait_by_id(self, bait_id: int) -> Optional[Bait]: pass
    # 获取所有鱼饵模板
    @abstractmethod
    def get_all_baits(self) -> List[Bait]: pass
    # 获取饰品模板
    @abstractmethod
    def get_accessory_by_id(self, accessory_id: int) -> Optional[Accessory]: pass
    # 获取所有饰品模板
    @abstractmethod
    def get_all_accessories(self) -> List[Accessory]: pass
    # 获取称号模板
    @abstractmethod
    def get_title_by_id(self, title_id: int) -> Optional[Title]: pass
    # 获取所有称号模板
    @abstractmethod
    def get_all_titles(self) -> List[Title]: pass
    # 随机获取一条鱼的模板
    @abstractmethod
    def get_random_fish(self, rarity: Optional[int] = None) -> Optional[Fish]: pass
    # 添加鱼类模板
    @abstractmethod
    def add_fish_template(self, fish_data: Dict[str, Any]) -> Fish: pass
    # 更新鱼类模板
    @abstractmethod
    def update_fish_template(self, fish_id: int, fish_data: Dict[str, Any]) -> None: pass
    # 删除鱼类模板
    @abstractmethod
    def delete_fish_template(self, fish_id: int) -> None: pass
    # 添加鱼饵模板
    @abstractmethod
    def add_bait_template(self, bait_data: Dict[str, Any]) -> Bait: pass
    # 更新鱼饵模板
    @abstractmethod
    def update_bait_template(self, bait_id: int, bait_data: Dict[str, Any]) -> None: pass
    # 删除鱼饵模板
    @abstractmethod
    def delete_bait_template(self, bait_id: int) -> None: pass
    # 添加鱼竿模板
    @abstractmethod
    def add_rod_template(self, rod_data: Dict[str, Any]) -> Rod: pass
    # 更新鱼竿模板
    @abstractmethod
    def update_rod_template(self, rod_id: int, rod_data: Dict[str, Any]) -> None: pass
    # 删除鱼竿模板
    @abstractmethod
    def delete_rod_template(self, rod_id: int) -> None: pass
    # 添加饰品模板
    @abstractmethod
    def add_accessory_template(self, accessory_data: Dict[str, Any]) -> Accessory: pass
    # 更新饰品模板
    @abstractmethod
    def update_accessory_template(self, accessory_id: int, accessory_data: Dict[str, Any]) -> None: pass
    # 删除饰品模板
    @abstractmethod
    def delete_accessory_template(self, accessory_id: int) -> None: pass
    # 添加称号模板
    @abstractmethod
    def add_title_template(self, title_data: Dict[str, Any]) -> Title: pass

class AbstractInventoryRepository(ABC):
    """用户库存仓储接口"""
    # 获取用户的鱼类库存
    @abstractmethod
    def get_fish_inventory(self, user_id: str) -> List[UserFishInventoryItem]: pass
    # 获取用户鱼类库存的总价值
    @abstractmethod
    def get_fish_inventory_value(self, user_id: str, rarity: Optional[int] = None) -> int: pass
    # 向用户鱼类库存添加鱼
    @abstractmethod
    def add_fish_to_inventory(self, user_id: str, fish_id: int, quantity: int = 1) -> None: pass
    # 清空用户鱼类库存
    @abstractmethod
    def clear_fish_inventory(self, user_id: str, rarity: Optional[int] = None) -> None: pass
    # 卖出所有鱼，每种保留一条
    @abstractmethod
    def sell_fish_keep_one(self, user_id: str) -> int: pass
    # 获取用户的鱼饵库存
    @abstractmethod
    def get_user_bait_inventory(self, user_id: str) -> Dict[int, int]: pass
    # 随机获取一个用户的鱼饵
    @abstractmethod
    def get_random_bait(self, user_id: str) -> Optional[int]: pass
    # 更新用户的鱼饵数量
    @abstractmethod
    def update_bait_quantity(self, user_id: str, bait_id: int, delta: int) -> None: pass
    # 获取用户的所有鱼竿实例
    @abstractmethod
    def get_user_rod_instances(self, user_id: str) -> List[UserRodInstance]: pass
    # 为用户添加一个鱼竿实例
    @abstractmethod
    def add_rod_instance(self, user_id: str, rod_id: int, durability: Optional[int], refine_level: int = 1) -> UserRodInstance: pass
    # 删除一个鱼竿实例
    @abstractmethod
    def delete_rod_instance(self, rod_instance_id: int) -> None: pass
    # 获取用户当前装备的鱼竿
    @abstractmethod
    def get_user_equipped_rod(self, user_id: str) -> Optional[UserRodInstance]: pass
    # 根据user_id 和 rod_instance_id 获取用户的鱼竿实例
    @abstractmethod
    def get_user_rod_instance_by_id(self, user_id: str, rod_instance_id: int) -> Optional[UserRodInstance]: pass
    # 清除用户的所有鱼竿实例（未装备和五星）
    @abstractmethod
    def clear_user_rod_instances(self, user_id: str) -> None: pass
    # 清除用户的所有饰品实例（未装备和五星）
    @abstractmethod
    def clear_user_accessory_instances(self, user_id: str) -> None: pass
    # 根据 user_id 和 accessory_instance_id 获取用户的饰品实例
    @abstractmethod
    def get_user_accessory_instance_by_id(self, user_id: str, accessory_instance_id: int) -> Optional[UserAccessoryInstance]: pass
    # 获取用户当前装备的饰品
    @abstractmethod
    def get_user_equipped_accessory(self, user_id: str) -> Optional[UserAccessoryInstance]: pass
    # 统一设置用户的装备状态
    @abstractmethod
    def set_equipment_status(self, user_id: str, rod_instance_id: Optional[int] = None, accessory_instance_id: Optional[int] = None) -> None: pass
    # 获取用户所有一次性鱼饵
    @abstractmethod
    def get_user_disposable_baits(self, user_id: str) -> Dict[int, int]: pass
    # 获取用户拥有的所有称号
    @abstractmethod
    def get_user_titles(self, user_id: str) -> List[int]: pass
    # 获取用户的所有鱼竿实例
    @abstractmethod
    def get_user_accessory_instances(self, user_id: str) -> List[UserAccessoryInstance]: pass
    # 新增一个饰品实例
    @abstractmethod
    def add_accessory_instance(self, user_id: str, accessory_id: int, refine_level: int = 1) -> UserAccessoryInstance: pass
    # 删除一个饰品实例
    @abstractmethod
    def delete_accessory_instance(self, accessory_instance_id: int) -> None: pass
    # 更新用户鱼类数量(增减)
    @abstractmethod
    def update_fish_quantity(self, user_id: str, fish_id: int, delta: int) -> None: pass
    # 获取钓鱼区域信息
    @abstractmethod
    def get_zone_by_id(self, zone_id: int) -> FishingZone: pass
    # 更新钓鱼区域信息
    @abstractmethod
    def update_fishing_zone(self, zone: FishingZone) -> None: pass
    # 获取所有钓鱼区域
    @abstractmethod
    def get_all_fishing_zones(self) -> List[FishingZone]: pass
    # 获取用户的鱼竿实例
    @abstractmethod
    def update_rod_instance(self, instance): pass
    # 获取用户的饰品实例
    @abstractmethod
    def update_accessory_instance(self, instance): pass
    # 获取用户的同一鱼竿实例
    @abstractmethod
    def get_same_rod_instances(self, user_id, rod_id) -> List[UserRodInstance]: pass
    # 获取用户的同一饰品实例
    @abstractmethod
    def get_same_accessory_instances(self, user_id, accessory_id) -> List[UserAccessoryInstance]: pass


class AbstractGachaRepository(ABC):
    """抽卡仓储接口"""
    # 获取抽卡池信息
    @abstractmethod
    def get_pool_by_id(self, pool_id: int) -> Optional[GachaPool]: pass
    # 获取抽卡池内的所有物品
    @abstractmethod
    def get_pool_items(self, pool_id: int) -> List[GachaPoolItem]: pass
    # 获取所有抽卡池
    @abstractmethod
    def get_all_pools(self) -> List[GachaPool]: pass
    # 新增一个抽卡池
    @abstractmethod
    def add_pool_template(self, data: Dict[str, Any]) -> GachaPool: pass
    # 更新抽卡池信息
    @abstractmethod
    def update_pool_template(self, pool_id: int, data: Dict[str, Any]) -> None: pass
    # 删除抽卡池
    @abstractmethod
    def delete_pool_template(self, pool_id: int) -> None: pass
    # 添加物品到抽卡池
    @abstractmethod
    def add_item_to_pool(self, pool_id: int, data: Dict[str, Any]) -> GachaPoolItem: pass
    # 更新抽卡池物品
    @abstractmethod
    def update_pool_item(self, item_pool_id: int, data: Dict[str, Any]) -> None: pass
    # 删除抽卡池物品
    @abstractmethod
    def delete_pool_item(self, item_pool_id: int) -> None: pass

class AbstractMarketRepository(ABC):
    """市场仓储接口"""
    # 获取单个市场商品
    @abstractmethod
    def get_listing_by_id(self, market_id: int) -> Optional[MarketListing]: pass
    # 获取所有市场商品
    @abstractmethod
    def get_all_listings(self, page: int = None, per_page: int = None, 
                        item_type: str = None, min_price: int = None, 
                        max_price: int = None, search: str = None) -> tuple: pass
    # 添加一个市场商品
    @abstractmethod
    def add_listing(self, listing: MarketListing) -> None: pass
    # 移除一个市场商品
    @abstractmethod
    def remove_listing(self, market_id: int) -> None: pass
    # 更新市场商品
    @abstractmethod
    def update_listing(self, listing: MarketListing) -> None: pass

class AbstractLogRepository(ABC):
    """日志类数据仓储接口"""
    # 记录一条钓鱼日志
    @abstractmethod
    def add_fishing_record(self, record: FishingRecord) -> bool: pass
    # 获取用户已经解锁的鱼类
    @abstractmethod
    def get_unlocked_fish_ids(self, user_id: str) -> Dict[int, datetime]: pass
    # 获取用户钓鱼日志
    @abstractmethod
    def get_fishing_records(self, user_id: str, limit: int) -> List[FishingRecord]: pass
    # 记录一条抽卡日志
    @abstractmethod
    def add_gacha_record(self, record: GachaRecord) -> None: pass
    # 获取用户抽卡日志
    @abstractmethod
    def get_gacha_records(self, user_id: str, limit: int) -> List[GachaRecord]: pass
    # 记录一条擦弹日志
    @abstractmethod
    def add_wipe_bomb_log(self, log: WipeBombLog) -> None: pass
    # 获取用户今日擦弹次数
    @abstractmethod
    def get_wipe_bomb_log_count_today(self, user_id: str) -> int: pass
    # 记录一条签到日志
    @abstractmethod
    def add_check_in(self, user_id: str, check_in_date: date) -> None: pass
    # 检查用户某天是否已签到
    @abstractmethod
    def has_checked_in(self, user_id: str, check_in_date: date) -> bool: pass
    # 记录一条税收日志
    @abstractmethod
    def add_tax_record(self, record: TaxRecord) -> None: pass
    # 获取用户的擦弹历史
    @abstractmethod
    def get_wipe_bomb_logs(self, user_id: str, limit: int = 10) -> List[WipeBombLog]: pass
    # 获取用户的税收历史
    @abstractmethod
    def get_tax_records(self, user_id: str, limit: int = 10) -> List[TaxRecord]: pass
    # 获取用户历史上最大的擦弹倍数
    @abstractmethod
    def get_max_wipe_bomb_multiplier(self, user_id: str) -> float: pass

class AbstractAchievementRepository(ABC):
    """成就数据仓储接口"""
    # 获取所有成就的模板信息
    @abstractmethod
    def get_all_achievements(self) -> List[Achievement]: pass
    # 获取指定用户的所有成就进度
    @abstractmethod
    def get_user_progress(self, user_id: str) -> UserAchievementProgress: pass
    # 创建或更新用户的成就进度
    @abstractmethod
    def update_user_progress(self, user_id: str, achievement_id: int, progress: int, completed_at: Optional[datetime]) -> None: pass
    # 授予用户一个称号
    @abstractmethod
    def grant_title_to_user(self, user_id: str, title_id: int) -> None: pass
    # 获取用户钓到的不同鱼种数量
    @abstractmethod
    def get_user_unique_fish_count(self, user_id: str) -> int: pass
    # 获取用户钓到的垃圾物品总数
    @abstractmethod
    def get_user_garbage_count(self, user_id: str) -> int: pass
    # 检查是否钓到过超过特定重量的鱼
    @abstractmethod
    def has_caught_heavy_fish(self, user_id: str, weight: int) -> bool: pass
    # 检查擦弹是否达到过特定倍率
    @abstractmethod
    def has_wipe_bomb_multiplier(self, user_id: str, multiplier: float) -> bool: pass
    # 检查用户是否拥有特定稀有度的物品
    @abstractmethod
    def has_item_of_rarity(self, user_id: str, item_type: str, rarity: int) -> bool: pass
