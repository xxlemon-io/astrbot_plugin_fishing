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
        self.shop_service = ShopService(self.item_template_repo, self.inventory_repo, self.user_repo)
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
        data_setup_service = DataSetupService(self.item_template_repo, self.gacha_repo)
        data_setup_service.setup_initial_data()
        # 确保初始道具存在（在已有数据库上也可幂等执行）
        try:
            data_setup_service.create_initial_items()
        except Exception:
            pass

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

        # 命令在类定义期通过装饰器静态注册

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

    # 工厂函数 + 装饰器：在类定义期静态注册命令，减少样板
    def _make_cmd(name, handler, alias=None, permission=None):
        async def _fn(self, event: AstrMessageEvent):
            async for r in handler(self, event):
                yield r
        fn = _fn
        if permission is not None:
            fn = filter.permission_type(permission)(fn)
        if alias is not None:
            fn = filter.command(name, alias=alias)(fn)
        else:
            fn = filter.command(name)(fn)
        return fn

    

    # =========== 背包与资产 ==========
    register_user = _make_cmd("注册", common_handlers.register_user)
    fish = _make_cmd("钓鱼", fishing_handlers.fish)
    sign_in = _make_cmd("签到", common_handlers.sign_in)
    auto_fish = _make_cmd("自动钓鱼", fishing_handlers.auto_fish)
    fishing_log = _make_cmd("钓鱼记录", common_handlers.fishing_log, alias={"钓鱼日志", "钓鱼历史"})
    state = _make_cmd("状态", common_handlers.state, alias={"我的状态"})
    fishing_help = _make_cmd("钓鱼帮助", common_handlers.fishing_help, alias={"钓鱼菜单", "菜单"})

    

    # =========== 钓鱼与图鉴 ==========
    fishing_area = _make_cmd("钓鱼区域", fishing_handlers.fishing_area, alias={"区域"})
    fish_pokedex = _make_cmd("鱼类图鉴", fishing_handlers.fish_pokedex)

    # =========== 市场与商店 ==========
    sell_all = _make_cmd("全部卖出", market_handlers.sell_all, alias={"全部出售", "卖出全部", "出售全部", "卖光", "清空鱼", "一键卖出"})
    sell_keep = _make_cmd("保留卖出", market_handlers.sell_keep, alias={"保留出售", "卖出保留", "出售保留", "留一卖出", "卖鱼留一"})
    sell_everything = _make_cmd("砸锅卖铁", market_handlers.sell_everything, alias={"破产", "清仓", "一键清空", "全部卖出装备", "卖光所有"})
    sell_by_rarity = _make_cmd("出售稀有度", market_handlers.sell_by_rarity, alias={"按稀有度出售", "稀有度出售", "卖稀有度", "出售星级", "按星级出售"})
    sell_rod = _make_cmd("出售鱼竿", market_handlers.sell_rod, alias={"卖出鱼竿", "卖鱼竿", "卖掉鱼竿"})
    sell_all_rods = _make_cmd("出售所有鱼竿", market_handlers.sell_all_rods, alias={"出售全部鱼竿", "卖出所有鱼竿", "卖出全部鱼竿", "卖光鱼竿", "清空鱼竿", "一键卖鱼竿"})
    sell_accessories = _make_cmd("出售饰品", market_handlers.sell_accessories, alias={"卖出饰品", "卖饰品", "卖掉饰品"})
    sell_all_accessories = _make_cmd("出售所有饰品", market_handlers.sell_all_accessories, alias={"出售全部饰品", "卖出所有饰品", "卖出全部饰品", "卖光饰品", "清空饰品", "一键卖饰品"})
    shop = _make_cmd("商店", market_handlers.shop)
    buy_rod = _make_cmd("购买鱼竿", market_handlers.buy_rod)
    buy_bait = _make_cmd("购买鱼饵", market_handlers.buy_bait)
    market = _make_cmd("市场", market_handlers.market)
    list_rod = _make_cmd("上架鱼竿", market_handlers.list_rod)
    list_accessories = _make_cmd("上架饰品", market_handlers.list_accessories)
    list_item = _make_cmd("上架道具", market_handlers.list_item)
    buy_item = _make_cmd("购买", market_handlers.buy_item)
    my_listings = _make_cmd("我的上架", market_handlers.my_listings, alias={"上架列表", "我的商品", "我的挂单"})
    delist_item = _make_cmd("下架", market_handlers.delist_item)

    # =========== 抽卡 ==========
    gacha = _make_cmd("抽卡", gacha_handlers.gacha, alias={"抽奖"})
    ten_gacha = _make_cmd("十连", gacha_handlers.ten_gacha)
    view_gacha_pool = _make_cmd("查看卡池", gacha_handlers.view_gacha_pool)
    gacha_history = _make_cmd("抽卡记录", gacha_handlers.gacha_history)
    wipe_bomb = _make_cmd("擦弹", gacha_handlers.wipe_bomb)
    wipe_bomb_history = _make_cmd("擦弹记录", gacha_handlers.wipe_bomb_history, alias={"擦弹历史"})

    # =========== 社交 ==========
    ranking = _make_cmd("排行榜", social_handlers.ranking, alias={"phb"})
    steal_fish = _make_cmd("偷鱼", social_handlers.steal_fish)
    dispel_protection = _make_cmd("驱灵", social_handlers.dispel_protection)
    view_titles = _make_cmd("查看称号", social_handlers.view_titles, alias={"称号"})
    use_title = _make_cmd("使用称号", social_handlers.use_title)
    view_achievements = _make_cmd("查看成就", social_handlers.view_achievements, alias={"成就"})
    tax_record = _make_cmd("税收记录", social_handlers.tax_record)

    # =========== 管理后台 ==========
    modify_coins = _make_cmd("修改金币", admin_handlers.modify_coins, permission=PermissionType.ADMIN)
    modify_premium = _make_cmd("修改高级货币", admin_handlers.modify_premium, permission=PermissionType.ADMIN)
    reward_premium = _make_cmd("奖励高级货币", admin_handlers.reward_premium, permission=PermissionType.ADMIN)
    deduct_premium = _make_cmd("扣除高级货币", admin_handlers.deduct_premium, permission=PermissionType.ADMIN)
    reward_all_coins = _make_cmd("全体奖励金币", admin_handlers.reward_all_coins, permission=PermissionType.ADMIN)
    reward_all_premium = _make_cmd("全体奖励高级货币", admin_handlers.reward_all_premium, permission=PermissionType.ADMIN)
    deduct_all_coins = _make_cmd("全体扣除金币", admin_handlers.deduct_all_coins, permission=PermissionType.ADMIN)
    deduct_all_premium = _make_cmd("全体扣除高级货币", admin_handlers.deduct_all_premium, permission=PermissionType.ADMIN)
    reward_coins = _make_cmd("奖励金币", admin_handlers.reward_coins, permission=PermissionType.ADMIN)
    deduct_coins = _make_cmd("扣除金币", admin_handlers.deduct_coins, permission=PermissionType.ADMIN)
    start_admin = _make_cmd("开启钓鱼后台管理", admin_handlers.start_admin, permission=PermissionType.ADMIN)
    stop_admin = _make_cmd("关闭钓鱼后台管理", admin_handlers.stop_admin, permission=PermissionType.ADMIN)
    sync_items_from_initial_data = _make_cmd("同步道具", admin_handlers.sync_items_from_initial_data, alias={"管理员 同步道具"}, permission=PermissionType.ADMIN)
    impersonate_start = _make_cmd("代理上线", admin_handlers.impersonate_start, permission=PermissionType.ADMIN)
    impersonate_stop = _make_cmd("代理下线", admin_handlers.impersonate_stop, permission=PermissionType.ADMIN)

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
    @filter.command("同步道具", alias={"管理员 同步道具"})
    async def sync_items_from_initial_data(self, event: AstrMessageEvent):
        async for r in admin_handlers.sync_items_from_initial_data(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("代理上线")
    async def impersonate_start(self, event: AstrMessageEvent):
        async for r in admin_handlers.impersonate_start(self, event):
            yield r

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("代理下线")
    async def impersonate_stop(self, event: AstrMessageEvent):
        async for r in admin_handlers.impersonate_stop(self, event):
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

