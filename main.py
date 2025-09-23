import os
import asyncio

from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.permission import PermissionType

# ==========================================================
# 导入所有仓储层 & 服务层（与旧版保持一致的精确导入）
# ==========================================================
from .core.repositories.sqlite_user_repo import SqliteUserRepository
from .core.repositories.sqlite_item_template_repo import SqliteItemTemplateRepository
from .core.repositories.sqlite_inventory_repo import SqliteInventoryRepository
from .core.repositories.sqlite_gacha_repo import SqliteGachaRepository
from .core.repositories.sqlite_market_repo import SqliteMarketRepository
from .core.repositories.sqlite_shop_repo import SqliteShopRepository
from .core.repositories.sqlite_log_repo import SqliteLogRepository
from .core.repositories.sqlite_achievement_repo import SqliteAchievementRepository
from .core.repositories.sqlite_user_buff_repo import SqliteUserBuffRepository

from .core.services.data_setup_service import DataSetupService
from .core.services.item_template_service import ItemTemplateService
from .core.services.user_service import UserService
from .core.services.fishing_service import FishingService
from .core.services.inventory_service import InventoryService
from .core.services.shop_service import ShopService
from .core.services.market_service import MarketService
from .core.services.gacha_service import GachaService
from .core.services.achievement_service import AchievementService
from .core.services.game_mechanics_service import GameMechanicsService
from .core.services.effect_manager import EffectManager
from .core.services.fishing_zone_service import FishingZoneService

from .core.database.migration import run_migrations

# ==========================================================
# 导入所有指令函数
# ==========================================================
from .handlers import admin_handlers, common_handlers, inventory_handlers, fishing_handlers, market_handlers, social_handlers, gacha_handlers


class FishingPlugin(Star):

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)

        # --- 1. 加载配置 ---
        self.is_tax = config.get("is_tax", True)  # 是否开启税收
        self.threshold = config.get("threshold", 100000)  # 起征点
        self.step_coins = config.get("step_coins", 100000)
        self.step_rate = config.get("step_rate", 0.01)
        self.max_rate = config.get("max_rate", 0.2)  # 最大税率
        self.min_rate = config.get("min_rate", 0.05)  # 最小税率
        self.area2num = config.get("area2num", 2000)
        self.area3num = config.get("area3num", 500)
        
        # 插件ID
        self.plugin_id = "astrbot_plugin_fishing"

        # --- 1.1. 数据与临时文件路径管理 ---
        try:
            # 优先使用框架提供的 get_data_dir 方法
            self.data_dir = self.context.get_data_dir(self.plugin_id)
        except (AttributeError, TypeError):
            # 如果方法不存在或调用失败，则回退到旧的硬编码路径
            logger.warning(f"无法使用 self.context.get_data_dir('{self.plugin_id}'), 将回退到旧的 'data/' 目录。")
            self.data_dir = "data"
        
        self.tmp_dir = os.path.join(self.data_dir, "tmp")
        os.makedirs(self.tmp_dir, exist_ok=True)

        db_path = os.path.join(self.data_dir, "fish.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.game_config = {
            "fishing": {"cost": config.get("fish_cost", 10), "cooldown_seconds": config.get("fish_cooldown_seconds", 180)},
            "steal": {"cooldown_seconds": config.get("steal_cooldown", 1800)},
            "wipe_bomb": {"max_attempts_per_day": config.get("wipe_bomb_attempts", 3)},
            "pond_upgrades": [
                { "from": 480, "to": 999, "cost": 50000 },
                { "from": 999, "to": 9999, "cost": 500000 },
                { "from": 9999, "to": 99999, "cost": 50000000 },
                { "from": 99999, "to": 999999, "cost": 5000000000 },
            ],
            "sell_prices": {
                "rod": { "1": 100, "2": 500, "3": 2000, "4": 5000, "5": 10000 },
                "accessory": { "1": 100, "2": 500, "3": 2000, "4": 5000, "5": 10000 },
                "refine_multiplier": {
                    "1": 1.0, "2": 1.6, "3": 3.0, "4": 6.0, "5": 12.0,
                    "6": 25.0, "7": 55.0, "8": 125.0, "9": 280.0, "10": 660.0
                }
            }
        }
        
        # 初始化数据库模式
        plugin_root_dir = os.path.dirname(__file__)
        migrations_path = os.path.join(plugin_root_dir, "core", "database", "migrations")
        run_migrations(db_path, migrations_path)

        # --- 2. 组合根：实例化所有仓储层 ---
        self.user_repo = SqliteUserRepository(db_path)
        self.item_template_repo = SqliteItemTemplateRepository(db_path)
        self.inventory_repo = SqliteInventoryRepository(db_path)
        self.gacha_repo = SqliteGachaRepository(db_path)
        self.market_repo = SqliteMarketRepository(db_path)
        self.shop_repo = SqliteShopRepository(db_path)
        self.log_repo = SqliteLogRepository(db_path)
        self.achievement_repo = SqliteAchievementRepository(db_path)
        self.buff_repo = SqliteUserBuffRepository(db_path)

        # --- 3. 组合根：实例化所有服务层，并注入依赖 ---
        # 3.1 核心服务必须在效果管理器之前实例化，以解决依赖问题
        self.fishing_zone_service = FishingZoneService(self.item_template_repo, self.inventory_repo, self.game_config)
        self.game_mechanics_service = GameMechanicsService(self.user_repo, self.log_repo, self.inventory_repo,
                                                          self.item_template_repo, self.buff_repo, self.game_config)

        # 3.3 实例化其他核心服务
        self.gacha_service = GachaService(self.gacha_repo, self.user_repo, self.inventory_repo, self.item_template_repo,
                                         self.log_repo, self.achievement_repo)
        # UserService 依赖 GachaService，因此在 GachaService 之后实例化
        self.user_service = UserService(self.user_repo, self.log_repo, self.inventory_repo, self.item_template_repo, self.gacha_service, self.game_config)
        self.inventory_service = InventoryService(
            self.inventory_repo,
            self.user_repo,
            self.item_template_repo,
            None,  # 先设为None，稍后设置
            self.game_mechanics_service,
            self.game_config,
        )
        self.shop_service = ShopService(self.item_template_repo, self.inventory_repo, self.user_repo, self.shop_repo, self.game_config)
        self.market_service = MarketService(self.market_repo, self.inventory_repo, self.user_repo, self.log_repo,
                                           self.item_template_repo, self.game_config)
        self.achievement_service = AchievementService(self.achievement_repo, self.user_repo, self.inventory_repo,
                                                     self.item_template_repo, self.log_repo)
        self.fishing_service = FishingService(
            self.user_repo,
            self.inventory_repo,
            self.item_template_repo,
            self.log_repo,
            self.buff_repo,
            self.fishing_zone_service,
            self.game_config,
        )

        # 3.2 实例化效果管理器并自动注册所有效果（需要在fishing_service之后）
        self.effect_manager = EffectManager()
        self.effect_manager.discover_and_register(
            effects_package_path="data.plugins.astrbot_plugin_fishing.core.services.item_effects",
            dependencies={
                "user_repo": self.user_repo, 
                "buff_repo": self.buff_repo,
                "game_mechanics_service": self.game_mechanics_service,
                "fishing_service": self.fishing_service,
                "log_repo": self.log_repo,
                "game_config": self.game_config,
            },
        )
        
        # 设置inventory_service的effect_manager
        self.inventory_service.effect_manager = self.effect_manager

        self.item_template_service = ItemTemplateService(self.item_template_repo, self.gacha_repo)

        # --- 4. 启动后台任务 ---
        self.fishing_service.start_auto_fishing_task()
        self.achievement_service.start_achievement_check_task()

        # --- 5. 初始化核心游戏数据 ---
        data_setup_service = DataSetupService(
            self.item_template_repo, self.gacha_repo, self.shop_repo
        )
        data_setup_service.setup_initial_data()
        # 确保初始道具存在（在已有数据库上也可幂等执行）
        try:
            data_setup_service.create_initial_items()
        except Exception:
            pass

        # 商店完全由后台管控，不再自动种子化

        # --- 6. (临时) 实例化数据服务，供调试命令使用 ---
        self.data_setup_service = data_setup_service

        # --- Web后台配置 ---
        self.web_admin_task = None
        self.secret_key = config.get("secret_key")
        if not self.secret_key:
            logger.error("安全警告：Web后台管理的'secret_key'未在配置中设置！强烈建议您设置一个长且随机的字符串以保证安全。")
            self.secret_key = None
        self.port = config.get("port", 7777)

        # 管理员扮演功能
        self.impersonation_map = {}

    def _get_effective_user_id(self, event: AstrMessageEvent):
        """获取在当前上下文中应当作为指令执行者的用户ID。
        - 默认返回消息发送者ID
        - 若发送者是管理员且已开启代理，则返回被代理用户ID
        注意：仅在非管理员指令中调用该方法；管理员指令应使用真实管理员ID。
        """
        admin_id = event.get_sender_id()
        return self.impersonation_map.get(admin_id, admin_id)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        logger.info("""
    _____ _     _     _
    |  ___(_)___| |__ (_)_ __   __ _
    | |_  | / __| '_ \\| | '_ \\ / _` |
    |  _| | \\__ \\ | | | | | | | (_| |
    |_|   |_|___/_| |_|_|_| |_|\\__, |
                               |___/
                               """)

    # =========== 基础与核心 ==========

    @filter.command("注册")
    async def register_user(self, event: AstrMessageEvent):
        async for r in common_handlers.register_user(self, event):
            yield r

    @filter.command("钓鱼")
    async def fish(self, event: AstrMessageEvent):
        async for r in fishing_handlers.fish(self, event):
            yield r

    @filter.command("签到")
    async def sign_in(self, event: AstrMessageEvent):
        async for r in common_handlers.sign_in(self, event):
            yield r

    @filter.command("自动钓鱼")
    async def auto_fish(self, event: AstrMessageEvent):
        async for r in fishing_handlers.auto_fish(self, event):
            yield r

    @filter.command("钓鱼记录", alias={"钓鱼日志", "钓鱼历史"})
    async def fishing_log(self, event: AstrMessageEvent):
        async for r in common_handlers.fishing_log(self, event):
            yield r

    @filter.command("状态", alias={"我的状态"})
    async def state(self, event: AstrMessageEvent):
        async for r in common_handlers.state(self, event):
            yield r

    @filter.command("钓鱼帮助", alias={"钓鱼菜单", "菜单"})
    async def fishing_help(self, event: AstrMessageEvent):
        async for r in common_handlers.fishing_help(self, event):
            yield r

    # =========== 背包与资产 ==========

    @filter.command("背包", alias={"查看背包", "我的背包"})
    async def user_backpack(self, event: AstrMessageEvent):
        async for r in inventory_handlers.user_backpack(self, event):
            yield r

    @filter.command("鱼塘")
    async def pond(self, event: AstrMessageEvent):
        async for r in inventory_handlers.pond(self, event):
            yield r

    @filter.command("鱼塘容量")
    async def pond_capacity(self, event: AstrMessageEvent):
        async for r in inventory_handlers.pond_capacity(self, event):
            yield r

    @filter.command("升级鱼塘", alias={"鱼塘升级"})
    async def upgrade_pond(self, event: AstrMessageEvent):
        async for r in inventory_handlers.upgrade_pond(self, event):
            yield r

    @filter.command("鱼竿")
    async def rod(self, event: AstrMessageEvent):
        async for r in inventory_handlers.rod(self, event):
            yield r

    @filter.command("精炼", alias={"强化"})
    async def refine_equipment(self, event: AstrMessageEvent):
        async for r in inventory_handlers.refine_equipment(self, event):
            yield r

    @filter.command("精炼鱼竿", alias={"鱼竿精炼"})
    async def refine_rod(self, event: AstrMessageEvent):
        async for r in inventory_handlers.refine_rod(self, event):
            yield r

    @filter.command("鱼饵")
    async def bait(self, event: AstrMessageEvent):
        async for r in inventory_handlers.bait(self, event):
            yield r

    @filter.command("道具", alias={"我的道具", "查看道具"})
    async def items(self, event: AstrMessageEvent):
        async for r in inventory_handlers.items(self, event):
            yield r

    @filter.command("使用道具")
    async def use_item(self, event: AstrMessageEvent):
        async for r in inventory_handlers.use_item(self, event):
            yield r

    @filter.command("开启全部钱袋", alias={"打开全部钱袋", "打开所有钱袋"})
    async def open_all_money_bags(self, event: AstrMessageEvent):
        async for r in inventory_handlers.open_all_money_bags(self, event):
            yield r

    @filter.command("出售道具", alias={"卖出道具"})
    async def sell_item(self, event: AstrMessageEvent):
        async for r in inventory_handlers.sell_item(self, event):
            yield r

    @filter.command("饰品")
    async def accessories(self, event: AstrMessageEvent):
        async for r in inventory_handlers.accessories(self, event):
            yield r

    @filter.command("精炼饰品", alias={"饰品精炼"})
    async def refine_accessory(self, event: AstrMessageEvent):
        async for r in inventory_handlers.refine_accessory(self, event):
            yield r

    @filter.command("精炼帮助", alias={"精炼说明"})
    async def refine_help(self, event: AstrMessageEvent):
        async for r in inventory_handlers.refine_help(self, event):
            yield r

    @filter.command("锁定", alias={"上锁"})
    async def lock_equipment(self, event: AstrMessageEvent):
        async for r in inventory_handlers.lock_equipment(self, event):
            yield r

    @filter.command("解锁", alias={"开锁"})
    async def unlock_equipment(self, event: AstrMessageEvent):
        async for r in inventory_handlers.unlock_equipment(self, event):
            yield r

    @filter.command("锁定鱼竿", alias={"鱼竿锁定"})
    async def lock_rod(self, event: AstrMessageEvent):
        async for r in inventory_handlers.lock_rod(self, event):
            yield r

    @filter.command("解锁鱼竿", alias={"鱼竿解锁"})
    async def unlock_rod(self, event: AstrMessageEvent):
        async for r in inventory_handlers.unlock_rod(self, event):
            yield r

    @filter.command("锁定饰品", alias={"饰品锁定"})
    async def lock_accessory(self, event: AstrMessageEvent):
        async for r in inventory_handlers.lock_accessory(self, event):
            yield r

    @filter.command("解锁饰品", alias={"饰品解锁"})
    async def unlock_accessory(self, event: AstrMessageEvent):
        async for r in inventory_handlers.unlock_accessory(self, event):
            yield r

    @filter.command("使用", alias={"装备"})
    async def use_equipment(self, event: AstrMessageEvent):
        async for r in inventory_handlers.use_equipment(self, event):
            yield r

    @filter.command("使用鱼竿", alias={"装备鱼竿"})
    async def use_rod(self, event: AstrMessageEvent):
        async for r in inventory_handlers.use_rod(self, event):
            yield r

    @filter.command("使用鱼饵", alias={"装备鱼饵"})
    async def use_bait(self, event: AstrMessageEvent):
        async for r in inventory_handlers.use_bait(self, event):
            yield r

    @filter.command("使用饰品", alias={"装备饰品"})
    async def use_accessories(self, event: AstrMessageEvent):
        async for r in inventory_handlers.use_accessories(self, event):
            yield r

    @filter.command("金币")
    async def coins(self, event: AstrMessageEvent):
        async for r in inventory_handlers.coins(self, event):
            yield r

    @filter.command("高级货币", alias={"钻石", "星石"})
    async def premium(self, event: AstrMessageEvent):
        async for r in inventory_handlers.premium(self, event):
            yield r

    # =========== 钓鱼与图鉴 ==========

    @filter.command("钓鱼区域", alias={"区域"})
    async def fishing_area(self, event: AstrMessageEvent):
        async for r in fishing_handlers.fishing_area(self, event):
            yield r

    @filter.command("鱼类图鉴", alias={"图鉴"})
    async def fish_pokedex(self, event: AstrMessageEvent):
        async for r in fishing_handlers.fish_pokedex(self, event):
            yield r

    # =========== 市场与商店 ==========

    @filter.command("全部卖出", alias={"全部出售", "卖出全部", "出售全部", "清空鱼"})
    async def sell_all(self, event: AstrMessageEvent):
        async for r in market_handlers.sell_all(self, event):
            yield r

    @filter.command("保留卖出", alias={"保留出售", "卖出保留", "出售保留"})
    async def sell_keep(self, event: AstrMessageEvent):
        async for r in market_handlers.sell_keep(self, event):
            yield r

    @filter.command("砸锅卖铁", alias={"破产", "清空", "清仓"})
    async def sell_everything(self, event: AstrMessageEvent):
        async for r in market_handlers.sell_everything(self, event):
            yield r

    @filter.command("出售稀有度", alias={"稀有度出售", "出售星级"})
    async def sell_by_rarity(self, event: AstrMessageEvent):
        async for r in market_handlers.sell_by_rarity(self, event):
            yield r

    @filter.command("出售鱼竿", alias={"卖出鱼竿"})
    async def sell_rod(self, event: AstrMessageEvent):
        async for r in market_handlers.sell_rod(self, event):
            yield r

    @filter.command("出售所有鱼竿", alias={"出售全部鱼竿", "卖出所有鱼竿", "卖出全部鱼竿", "清空鱼竿"})
    async def sell_all_rods(self, event: AstrMessageEvent):
        async for r in market_handlers.sell_all_rods(self, event):
            yield r

    @filter.command("出售饰品", alias={"卖出饰品", "卖饰品", "卖掉饰品"})
    async def sell_accessories(self, event: AstrMessageEvent):
        async for r in market_handlers.sell_accessories(self, event):
            yield r

    @filter.command("出售所有饰品", alias={"出售全部饰品", "卖出所有饰品", "卖出全部饰品", "清空饰品"})
    async def sell_all_accessories(self, event: AstrMessageEvent):
        async for r in market_handlers.sell_all_accessories(self, event):
            yield r

    @filter.command("商店")
    async def shop(self, event: AstrMessageEvent):
        async for r in market_handlers.shop(self, event):
            yield r

    

    @filter.command("商店购买", alias={"购买商店商品", "购买商店"})
    async def buy_in_shop(self, event: AstrMessageEvent):
        async for r in market_handlers.buy_in_shop(self, event):
            yield r

    @filter.command("市场")
    async def market(self, event: AstrMessageEvent):
        async for r in market_handlers.market(self, event):
            yield r

    @filter.command("上架")
    async def list_any(self, event: AstrMessageEvent):
        async for r in market_handlers.list_any(self, event):
            yield r

    @filter.command("上架鱼竿")
    async def list_rod(self, event: AstrMessageEvent):
        async for r in market_handlers.list_rod(self, event):
            yield r

    @filter.command("上架饰品")
    async def list_accessories(self, event: AstrMessageEvent):
        async for r in market_handlers.list_accessories(self, event):
            yield r

    @filter.command("上架道具")
    async def list_item(self, event: AstrMessageEvent):
        async for r in market_handlers.list_item(self, event):
            yield r

    @filter.command("匿名上架鱼竿", alias={"匿名上架竿", "匿名挂竿"})
    async def anonymous_list_rod(self, event: AstrMessageEvent):
        async for r in market_handlers.anonymous_list_rod(self, event):
            yield r

    @filter.command("匿名上架")
    async def anonymous_list_any(self, event: AstrMessageEvent):
        async for r in market_handlers.anonymous_list_any(self, event):
            yield r

    @filter.command("匿名上架饰品", alias={"匿名上架饰", "匿名挂饰"})
    async def anonymous_list_accessories(self, event: AstrMessageEvent):
        async for r in market_handlers.anonymous_list_accessories(self, event):
            yield r

    @filter.command("匿名上架道具", alias={"匿名上架物", "匿名挂物"})
    async def anonymous_list_item(self, event: AstrMessageEvent):
        async for r in market_handlers.anonymous_list_item(self, event):
            yield r

    @filter.command("购买")
    async def buy_item(self, event: AstrMessageEvent):
        async for r in market_handlers.buy_item(self, event):
            yield r

    @filter.command("我的上架", alias={"上架列表", "我的商品", "我的挂单"})
    async def my_listings(self, event: AstrMessageEvent):
        async for r in market_handlers.my_listings(self, event):
            yield r

    @filter.command("下架")
    async def delist_item(self, event: AstrMessageEvent):
        async for r in market_handlers.delist_item(self, event):
            yield r

    # =========== 抽卡 ==========

    @filter.command("抽卡", alias={"抽奖"})
    async def gacha(self, event: AstrMessageEvent):
        async for r in gacha_handlers.gacha(self, event):
            yield r

    @filter.command("十连")
    async def ten_gacha(self, event: AstrMessageEvent):
        async for r in gacha_handlers.ten_gacha(self, event):
            yield r

    @filter.command("查看卡池", alias={"卡池"})
    async def view_gacha_pool(self, event: AstrMessageEvent):
        async for r in gacha_handlers.view_gacha_pool(self, event):
            yield r

    @filter.command("抽卡记录")
    async def gacha_history(self, event: AstrMessageEvent):
        async for r in gacha_handlers.gacha_history(self, event):
            yield r

    @filter.command("擦弹")
    async def wipe_bomb(self, event: AstrMessageEvent):
        async for r in gacha_handlers.wipe_bomb(self, event):
            yield r

    @filter.command("擦弹记录", alias={"擦弹历史"})
    async def wipe_bomb_history(self, event: AstrMessageEvent):
        async for r in gacha_handlers.wipe_bomb_history(self, event):
            yield r

    # =========== 社交 ==========

    @filter.command("排行榜", alias={"phb"})
    async def ranking(self, event: AstrMessageEvent):
        async for r in social_handlers.ranking(self, event):
            yield r

    @filter.command("偷鱼")
    async def steal_fish(self, event: AstrMessageEvent):
        async for r in social_handlers.steal_fish(self, event):
            yield r

    @filter.command("驱灵")
    async def dispel_protection(self, event: AstrMessageEvent):
        async for r in social_handlers.dispel_protection(self, event):
            yield r

    @filter.command("查看称号", alias={"称号"})
    async def view_titles(self, event: AstrMessageEvent):
        async for r in social_handlers.view_titles(self, event):
            yield r

    @filter.command("使用称号")
    async def use_title(self, event: AstrMessageEvent):
        async for r in social_handlers.use_title(self, event):
            yield r

    @filter.command("查看成就", alias={"成就"})
    async def view_achievements(self, event: AstrMessageEvent):
        async for r in social_handlers.view_achievements(self, event):
            yield r

    @filter.command("税收记录")
    async def tax_record(self, event: AstrMessageEvent):
        async for r in social_handlers.tax_record(self, event):
            yield r

    # =========== 管理后台 ==========

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("修改金币")
    async def modify_coins(self, event: AstrMessageEvent):
        async for r in admin_handlers.modify_coins(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("修改高级货币")
    async def modify_premium(self, event: AstrMessageEvent):
        async for r in admin_handlers.modify_premium(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("奖励高级货币")
    async def reward_premium(self, event: AstrMessageEvent):
        async for r in admin_handlers.reward_premium(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("扣除高级货币")
    async def deduct_premium(self, event: AstrMessageEvent):
        async for r in admin_handlers.deduct_premium(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体奖励金币")
    async def reward_all_coins(self, event: AstrMessageEvent):
        async for r in admin_handlers.reward_all_coins(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体奖励高级货币")
    async def reward_all_premium(self, event: AstrMessageEvent):
        async for r in admin_handlers.reward_all_premium(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体扣除金币")
    async def deduct_all_coins(self, event: AstrMessageEvent):
        async for r in admin_handlers.deduct_all_coins(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体扣除高级货币")
    async def deduct_all_premium(self, event: AstrMessageEvent):
        async for r in admin_handlers.deduct_all_premium(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("奖励金币")
    async def reward_coins(self, event: AstrMessageEvent):
        async for r in admin_handlers.reward_coins(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("扣除金币")
    async def deduct_coins(self, event: AstrMessageEvent):
        async for r in admin_handlers.deduct_coins(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("开启钓鱼后台管理")
    async def start_admin(self, event: AstrMessageEvent):
        async for r in admin_handlers.start_admin(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("关闭钓鱼后台管理")
    async def stop_admin(self, event: AstrMessageEvent):
        async for r in admin_handlers.stop_admin(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("同步初始设定", alias={"同步设定", "同步数据", "同步"})
    async def sync_initial_data(self, event: AstrMessageEvent):
        async for r in admin_handlers.sync_initial_data(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("代理上线", alias={"login"})
    async def impersonate_start(self, event: AstrMessageEvent):
        async for r in admin_handlers.impersonate_start(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("代理下线", alias={"logout"})
    async def impersonate_stop(self, event: AstrMessageEvent):
        async for r in admin_handlers.impersonate_stop(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体发放道具")
    async def reward_all_items(self, event: AstrMessageEvent):
        async for r in admin_handlers.reward_all_items(self, event):
            yield r

    async def _check_port_active(self):
        """验证端口是否实际已激活"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", self.port),
                timeout=1
            )
            writer.close()
            return True
        except:  # noqa: E22
            return False

    async def terminate(self):
        """插件被卸载/停用时调用"""
        logger.info("钓鱼插件正在终止...")
        self.fishing_service.stop_auto_fishing_task()
        self.achievement_service.stop_achievement_check_task()
        if self.web_admin_task:
            self.web_admin_task.cancel()
        logger.info("钓鱼插件已成功终止。")

