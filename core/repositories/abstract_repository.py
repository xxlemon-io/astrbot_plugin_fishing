from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import date, datetime

# 从领域模型导入所有需要的实体
from ..domain.models import (
    User, Fish, Rod, Bait, Accessory, Title, Achievement, Item,
    UserRodInstance, UserAccessoryInstance, UserFishInventoryItem, UserAquariumItem,
    FishingRecord, GachaRecord, WipeBombLog, MarketListing, TaxRecord,
    GachaPool, GachaPoolItem, FishingZone, UserBuff, AquariumUpgrade,
    ShopOffer, ShopOfferCost, ShopOfferReward,
    Commodity, Exchange, UserCommodity  # 新增交易所模型导入
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

    # 修改：用三个更具体的方法替换旧的 get_leaderboard_data
    @abstractmethod
    def get_top_users_by_fish_count(self, limit: int) -> List[User]:
        """按总钓鱼数获取排行榜用户列表。"""
        raise NotImplementedError

    @abstractmethod
    def get_top_users_by_coins(self, limit: int) -> List[User]:
        """按金币数获取排行榜用户列表。"""
        raise NotImplementedError

    @abstractmethod
    def get_top_users_by_max_coins(self, limit: int) -> List[User]:
        """按历史最高金币数获取排行榜用户列表。"""
        raise NotImplementedError

    @abstractmethod
    def get_top_users_by_weight(self, limit: int) -> List[User]:
        """按总重量获取排行榜用户列表。"""
        raise NotImplementedError

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
    # 获取道具模板
    @abstractmethod
    def get_item_by_id(self, item_id: int) -> Optional[Item]: pass
    # 获取所有道具模板
    @abstractmethod
    def get_all_items(self) -> List[Item]: pass
    # 添加道具模板
    @abstractmethod
    def add_item_template(self, item_data: Dict[str, Any]) -> Item: pass
    # 更新道具模板
    @abstractmethod
    def update_item_template(self, item_id: int, item_data: Dict[str, Any]) -> None: pass
    # 删除道具模板
    @abstractmethod
    def delete_item_template(self, item_id: int) -> None: pass
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
    # 更新称号模板
    @abstractmethod
    def update_title_template(self, title_id: int, title_data: Dict[str, Any]) -> None: pass
    # 删除称号模板
    @abstractmethod
    def delete_title_template(self, title_id: int) -> None: pass
    # 通过名称查找称号模板
    @abstractmethod
    def get_title_by_name(self, name: str) -> Optional[Title]: pass

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
    def add_fish_to_inventory(self, user_id: str, fish_id: int, quantity: int = 1, quality_level: int = 0) -> None: pass
    # 清空用户鱼类库存
    @abstractmethod
    def clear_fish_inventory(self, user_id: str, rarity: Optional[int] = None) -> None: pass
    # 更新用户鱼类库存数量
    @abstractmethod
    def update_fish_quantity(self, user_id: str, fish_id: int, delta: int, quality_level: int = 0) -> None: pass
    
    # --- 水族箱相关方法 ---
    # 获取用户水族箱中的鱼
    @abstractmethod
    def get_aquarium_inventory(self, user_id: str) -> List[UserAquariumItem]: pass
    # 获取用户水族箱中鱼的总价值
    @abstractmethod
    def get_aquarium_inventory_value(self, user_id: str, rarity: Optional[int] = None) -> int: pass
    # 向用户水族箱添加鱼
    @abstractmethod
    def add_fish_to_aquarium(self, user_id: str, fish_id: int, quantity: int = 1, quality_level: int = 0) -> None: pass
    # 从用户水族箱移除鱼
    @abstractmethod
    def remove_fish_from_aquarium(self, user_id: str, fish_id: int, quantity: int = 1, quality_level: int = 0) -> None: pass
    # 更新用户水族箱中鱼的数量
    @abstractmethod
    def update_aquarium_fish_quantity(self, user_id: str, fish_id: int, delta: int, quality_level: int = 0) -> None: pass
    # 清空用户水族箱
    @abstractmethod
    def clear_aquarium_inventory(self, user_id: str, rarity: Optional[int] = None) -> None: pass
    # 获取用户水族箱中鱼的总数量
    @abstractmethod
    def get_aquarium_total_count(self, user_id: str) -> int: pass
    # 获取用户指定鱼类的总数量（包括鱼塘和水族箱）
    @abstractmethod
    def get_user_total_fish_count(self, user_id: str, fish_id: int) -> int: pass
    # 智能扣除鱼类：优先从鱼塘扣除，不足时从水族箱扣除
    @abstractmethod
    def deduct_fish_smart(self, user_id: str, fish_id: int, quantity: int, quality_level: int = 0) -> None: pass
    # 获取所有水族箱升级配置
    @abstractmethod
    def get_aquarium_upgrades(self) -> List[AquariumUpgrade]: pass
    # 根据等级获取水族箱升级配置
    @abstractmethod
    def get_aquarium_upgrade_by_level(self, level: int) -> Optional[AquariumUpgrade]: pass
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
    # 获取用户的道具库存
    @abstractmethod
    def get_user_item_inventory(self, user_id: str) -> Dict[int, int]: pass
    # 更新用户的道具数量
    @abstractmethod
    def update_item_quantity(self, user_id: str, item_id: int, delta: int) -> None: pass
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
    def update_fish_quantity(self, user_id: str, fish_id: int, delta: int, quality_level: int = 0) -> None: pass
    # 获取钓鱼区域信息
    @abstractmethod
    def get_zone_by_id(self, zone_id: int) -> FishingZone: pass
    # 更新钓鱼区域信息
    @abstractmethod
    def update_fishing_zone(self, zone: FishingZone) -> None: pass
    # 获取所有钓鱼区域
    @abstractmethod
    def get_all_zones(self) -> List[FishingZone]: pass

    @abstractmethod
    def update_zone_configs(self, zone_id: int, configs: str) -> None: pass

    @abstractmethod
    def create_zone(self, zone_data: Dict[str, Any]) -> FishingZone: pass

    @abstractmethod
    def update_zone(self, zone_id: int, zone_data: Dict[str, Any]) -> None: pass

    @abstractmethod
    def delete_zone(self, zone_id: int) -> None: pass

    @abstractmethod
    def get_specific_fish_ids_for_zone(self, zone_id: int) -> List[int]: pass

    @abstractmethod
    def update_specific_fish_for_zone(self, zone_id: int, fish_ids: List[int]) -> None: pass

    # 获取用户的鱼竿实例
    @abstractmethod
    def update_rod_instance(self, instance): pass
    # 转移鱼竿实例所有权
    @abstractmethod
    def transfer_rod_instance_ownership(self, rod_instance_id: int, new_user_id: str) -> None: pass
    # 获取用户的饰品实例
    @abstractmethod
    def update_accessory_instance(self, instance): pass
    # 转移饰品实例所有权
    @abstractmethod
    def transfer_accessory_instance_ownership(self, accessory_instance_id: int, new_user_id: str) -> None: pass
    # 获取用户的同一鱼竿实例
    @abstractmethod
    def get_same_rod_instances(self, user_id, rod_id) -> List[UserRodInstance]: pass
    # 获取用户的同一饰品实例
    @abstractmethod
    def get_same_accessory_instances(self, user_id, accessory_id) -> List[UserAccessoryInstance]: pass

    @abstractmethod
    def add_item_to_user(self, user_id: str, item_id: int, quantity: int):
        pass

    @abstractmethod
    def decrease_item_quantity(self, user_id: str, item_id: int, quantity: int):
        pass


class AbstractExchangeRepository(ABC):
    """大宗商品交易所的数据仓储抽象基类"""

    @abstractmethod
    def get_all_commodities(self) -> List[Commodity]:
        """获取所有大宗商品的模板信息"""
        pass

    @abstractmethod
    def get_commodity_by_id(self, commodity_id: str) -> Optional[Commodity]:
        """通过ID获取单个大宗商品信息"""
        pass

    @abstractmethod
    def get_prices_for_date(self, date: str) -> List[Exchange]:
        """获取指定日期的所有商品价格"""
        pass

    @abstractmethod
    def add_exchange_price(self, price: Exchange) -> None:
        """新增一条交易所价格记录"""
        pass

    @abstractmethod
    def delete_prices_for_date(self, date: str) -> None:
        """删除指定日期的所有价格"""
        pass

    @abstractmethod
    def get_user_commodities(self, user_id: str) -> List[UserCommodity]:
        """获取用户持有的所有大宗商品"""
        pass

    @abstractmethod
    def add_user_commodity(self, user_commodity: UserCommodity) -> UserCommodity:
        """为用户新增大宗商品库存"""
        pass

    @abstractmethod
    def update_user_commodity_quantity(self, instance_id: int, new_quantity: int) -> None:
        """更新用户大宗商品的数量"""
        pass

    @abstractmethod
    def delete_user_commodity(self, instance_id: int) -> None:
        """删除用户的大宗商品库存"""
        pass

    @abstractmethod
    def get_user_commodity_by_instance_id(self, instance_id: int) -> Optional[UserCommodity]:
        """通过实例ID获取用户商品"""
        pass

    @abstractmethod
    def clear_expired_commodities(self, user_id: str) -> int:
        """清理用户库存中的腐败商品，返回清理的数量"""
        pass


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
    # 复制抽卡池
    @abstractmethod
    def copy_pool_template(self, pool_id: int) -> int: pass
    # 添加物品到抽卡池
    @abstractmethod
    def add_item_to_pool(self, pool_id: int, data: Dict[str, Any]) -> GachaPoolItem: pass
    # 更新抽卡池物品
    @abstractmethod
    def update_pool_item(self, item_pool_id: int, data: Dict[str, Any]) -> None: pass
    # 删除抽卡池物品
    @abstractmethod
    def delete_pool_item(self, item_pool_id: int) -> None: pass

    @abstractmethod
    def get_free_pools(self) -> List[GachaPool]:
        pass


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
    # 检查某个用户今天是否已经被征收过每日资产税
    @abstractmethod
    def has_user_daily_tax_today(self, user_id: str, reset_hour: int = 0) -> bool: pass
    # 获取用户历史上最大的擦弹倍数
    @abstractmethod
    def get_max_wipe_bomb_multiplier(self, user_id: str) -> float: pass
    @abstractmethod
    def get_min_wipe_bomb_multiplier(self, user_id: str) -> Optional[float]: pass

    @abstractmethod
    def get_gacha_records_count_today(
        self, user_id: str, gacha_pool_id: int
    ) -> int:
        pass

    @abstractmethod
    def add_log(self, user_id: str, log_type: str, message: str) -> None:
        """添加一条通用日志"""
        pass

    # --- 用户鱼类统计（用于图鉴与个人纪录） ---
    @abstractmethod
    def get_user_fish_stats(self, user_id: str) -> List["UserFishStat"]:
        pass

    @abstractmethod
    def get_user_fish_stat(self, user_id: str, fish_id: int) -> Optional["UserFishStat"]:
        pass

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
    # 移除用户的一个称号
    @abstractmethod
    def revoke_title_from_user(self, user_id: str, title_id: int) -> None: pass
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

class AbstractUserBuffRepository(ABC):
    @abstractmethod
    def add(self, buff: UserBuff):
        pass

    @abstractmethod
    def update(self, buff: UserBuff):
        pass

    @abstractmethod
    def get_active_by_user_and_type(
        self, user_id: str, buff_type: str
    ) -> Optional["UserBuff"]:
        pass

    @abstractmethod
    def get_all_active_by_user(self, user_id: str) -> List["UserBuff"]:
        pass

    @abstractmethod
    def delete_expired(self):
        pass

    @abstractmethod
    def delete(self, buff_id: int):
        pass


class AbstractShopRepository(ABC):
    """商店系统仓储接口（新设计：shops + shop_items + shop_item_costs + shop_item_rewards）"""

    # ---- 商店管理（Shops） ----
    @abstractmethod
    def get_active_shops(self, shop_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取活跃的商店列表"""
        pass

    @abstractmethod
    def get_all_shops(self) -> List[Dict[str, Any]]:
        """获取所有商店列表"""
        pass

    @abstractmethod
    def get_shop_by_id(self, shop_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取商店信息"""
        pass

    @abstractmethod
    def create_shop(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新商店"""
        pass

    @abstractmethod
    def update_shop(self, shop_id: int, data: Dict[str, Any]) -> None:
        """更新商店信息"""
        pass

    @abstractmethod
    def delete_shop(self, shop_id: int) -> None:
        """删除商店"""
        pass

    # ---- 商店商品管理（Shop Items） ----
    @abstractmethod
    def get_shop_items(self, shop_id: int) -> List[Dict[str, Any]]:
        """获取商店的所有商品"""
        pass

    @abstractmethod
    def get_shop_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取商店商品"""
        pass

    @abstractmethod
    def create_shop_item(self, shop_id: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建商店商品"""
        pass

    @abstractmethod
    def update_shop_item(self, item_id: int, data: Dict[str, Any]) -> None:
        """更新商店商品"""
        pass

    @abstractmethod
    def delete_shop_item(self, item_id: int) -> None:
        """删除商店商品"""
        pass

    @abstractmethod
    def increase_item_sold(self, item_id: int, delta: int) -> None:
        """增加商品销量"""
        pass

    # ---- 商品成本管理（Shop Item Costs） ----
    @abstractmethod
    def get_item_costs(self, item_id: int) -> List[Dict[str, Any]]:
        """获取商品的所有成本"""
        pass

    @abstractmethod
    def add_item_cost(self, item_id: int, cost_data: Dict[str, Any]) -> None:
        """添加商品成本"""
        pass

    @abstractmethod
    def update_item_cost(self, cost_id: int, data: Dict[str, Any]) -> None:
        """更新商品成本"""
        pass

    @abstractmethod
    def delete_item_cost(self, cost_id: int) -> None:
        """删除商品成本"""
        pass

    # ---- 商品奖励管理（Shop Item Rewards） ----
    @abstractmethod
    def get_item_rewards(self, item_id: int) -> List[Dict[str, Any]]:
        """获取商品的所有奖励"""
        pass

    @abstractmethod
    def add_item_reward(self, item_id: int, reward_data: Dict[str, Any]) -> None:
        """添加商品奖励"""
        pass

    @abstractmethod
    def update_item_reward(self, reward_id: int, data: Dict[str, Any]) -> None:
        """更新商品奖励"""
        pass

    @abstractmethod
    def delete_item_reward(self, reward_id: int) -> None:
        """删除商品奖励"""
        pass

    # ---- 购买记录管理（Shop Purchase Records） ----
    @abstractmethod
    def add_purchase_record(self, user_id: str, item_id: int, quantity: int) -> None:
        """记录购买"""
        pass

    @abstractmethod
    def get_user_purchased_count(self, user_id: str, item_id: int, since: Optional[datetime] = None) -> int:
        """获取用户购买数量（用于限购检查）"""
        pass

    @abstractmethod
    def get_user_purchase_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户购买历史"""
        pass

    # ---- 兼容性方法（向后兼容） ----
    @abstractmethod
    def get_active_offers(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取活跃商品（兼容旧接口）"""
        pass

    @abstractmethod
    def get_offer_by_id(self, offer_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取商品（兼容旧接口）"""
        pass