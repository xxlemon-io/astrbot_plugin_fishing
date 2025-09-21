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
    # ==========================================================
    # Admin Commands
    # ==========================================================
    modify_coins = filter.permission_type(PermissionType.ADMIN)(filter.command("修改金币")(admin_handlers.modify_coins))
    modify_premium = filter.permission_type(PermissionType.ADMIN)(filter.command("修改高级货币")(admin_handlers.modify_premium))
    reward_premium = filter.permission_type(PermissionType.ADMIN)(filter.command("奖励高级货币")(admin_handlers.reward_premium))
    deduct_premium = filter.permission_type(PermissionType.ADMIN)(filter.command("扣除高级货币")(admin_handlers.deduct_premium))
    reward_all_coins = filter.permission_type(PermissionType.ADMIN)(filter.command("全体奖励金币")(admin_handlers.reward_all_coins))
    reward_all_premium = filter.permission_type(PermissionType.ADMIN)(filter.command("全体奖励高级货币")(admin_handlers.reward_all_premium))
    deduct_all_coins = filter.permission_type(PermissionType.ADMIN)(filter.command("全体扣除金币")(admin_handlers.deduct_all_coins))
    deduct_all_premium = filter.permission_type(PermissionType.ADMIN)(filter.command("全体扣除高级货币")(admin_handlers.deduct_all_premium))
    reward_coins = filter.permission_type(PermissionType.ADMIN)(filter.command("奖励金币")(admin_handlers.reward_coins))
    deduct_coins = filter.permission_type(PermissionType.ADMIN)(filter.command("扣除金币")(admin_handlers.deduct_coins))
    start_admin = filter.permission_type(PermissionType.ADMIN)(filter.command("开启钓鱼后台管理")(admin_handlers.start_admin))
    stop_admin = filter.permission_type(PermissionType.ADMIN)(filter.command("关闭钓鱼后台管理")(admin_handlers.stop_admin))
    sync_items_from_initial_data = filter.permission_type(PermissionType.ADMIN)(filter.command("同步道具", alias={"管理员 同步道具"})(admin_handlers.sync_items_from_initial_data))
    impersonate_start = filter.permission_type(PermissionType.ADMIN)(filter.command("代理上线")(admin_handlers.impersonate_start))
    impersonate_stop = filter.permission_type(PermissionType.ADMIN)(filter.command("代理下线")(admin_handlers.impersonate_stop))

    # ==========================================================
    # Common Commands
    # ==========================================================
    register_user = filter.command("注册")(common_handlers.register_user)
    sign_in = filter.command("签到")(common_handlers.sign_in)
    state = filter.command("状态", alias={"我的状态"})(common_handlers.state)
    fishing_log = filter.command("钓鱼记录", alias={"钓鱼日志", "钓鱼历史"})(common_handlers.fishing_log)
    fishing_help = filter.command("钓鱼帮助", alias={"钓鱼菜单", "菜单"})(common_handlers.fishing_help)

    # ==========================================================
    # Inventory Commands
    # ==========================================================
    user_backpack = filter.command("背包", alias={"查看背包", "我的背包"})(inventory_handlers.user_backpack)
    pond = filter.command("鱼塘")(inventory_handlers.pond)
    pond_capacity = filter.command("鱼塘容量")(inventory_handlers.pond_capacity)
    upgrade_pond = filter.command("升级鱼塘", alias={"鱼塘升级"})(inventory_handlers.upgrade_pond)
    rod = filter.command("鱼竿")(inventory_handlers.rod)
    refine_rod = filter.command("精炼鱼竿", alias={"鱼竿精炼"})(inventory_handlers.refine_rod)
    bait = filter.command("鱼饵")(inventory_handlers.bait)
    items = filter.command("道具", alias={"我的道具", "查看道具"})(inventory_handlers.items)
    use_item = filter.command("使用道具", alias={"使用"})(inventory_handlers.use_item)
    sell_item = filter.command("卖道具", alias={"出售道具", "卖出道具"})(inventory_handlers.sell_item)
    accessories = filter.command("饰品")(inventory_handlers.accessories)
    refine_accessory = filter.command("精炼饰品", alias={"饰品精炼"})(inventory_handlers.refine_accessory)
    refine_help = filter.command("精炼帮助", alias={"精炼说明", "精炼"})(inventory_handlers.refine_help)
    lock_rod = filter.command("锁定鱼竿", alias={"鱼竿锁定"})(inventory_handlers.lock_rod)
    unlock_rod = filter.command("解锁鱼竿", alias={"鱼竿解锁"})(inventory_handlers.unlock_rod)
    lock_accessory = filter.command("锁定饰品", alias={"饰品锁定"})(inventory_handlers.lock_accessory)
    unlock_accessory = filter.command("解锁饰品", alias={"饰品解锁"})(inventory_handlers.unlock_accessory)
    use_rod = filter.command("使用鱼竿 ", alias={"装备鱼竿"})(inventory_handlers.use_rod)
    use_bait = filter.command("使用鱼饵", alias={"装备鱼饵"})(inventory_handlers.use_bait)
    use_accessories = filter.command("使用饰品", alias={"装备饰品"})(inventory_handlers.use_accessories)
    coins = filter.command("金币")(inventory_handlers.coins)
    premium = filter.command("高级货币", alias={"钻石", "星石"})(inventory_handlers.premium)

    # ==========================================================
    # Fishing Commands
    # ==========================================================
    fish = filter.command("钓鱼")(fishing_handlers.fish)
    auto_fish = filter.command("自动钓鱼")(fishing_handlers.auto_fish)
    fishing_area = filter.command("钓鱼区域", alias={"区域"})(fishing_handlers.fishing_area)
    fish_pokedex = filter.command("鱼类图鉴")(fishing_handlers.fish_pokedex)

    # ==========================================================
    # Market Commands
    # ==========================================================
    sell_all = filter.command("全部卖出", alias={"全部出售", "卖出全部", "出售全部", "卖光", "清空鱼", "一键卖出"})(market_handlers.sell_all)
    sell_keep = filter.command("保留卖出", alias={"保留出售", "卖出保留", "出售保留", "留一卖出", "卖鱼留一"})(market_handlers.sell_keep)
    sell_everything = filter.command("砸锅卖铁", alias={"破产", "清仓", "一键清空", "全部卖出装备", "卖光所有"})(market_handlers.sell_everything)
    sell_by_rarity = filter.command("出售稀有度", alias={"按稀有度出售", "稀有度出售", "卖稀有度", "出售星级", "按星级出售"})(market_handlers.sell_by_rarity)
    sell_rod = filter.command("出售鱼竿", alias={"卖出鱼竿", "卖鱼竿", "卖掉鱼竿"})(market_handlers.sell_rod)
    sell_all_rods = filter.command("出售所有鱼竿", alias={"出售全部鱼竿", "卖出所有鱼竿", "卖出全部鱼竿", "卖光鱼竿", "清空鱼竿", "一键卖鱼竿"})(market_handlers.sell_all_rods)
    sell_accessories = filter.command("出售饰品", alias={"卖出饰品", "卖饰品", "卖掉饰品"})(market_handlers.sell_accessories)
    sell_all_accessories = filter.command("出售所有饰品", alias={"出售全部饰品", "卖出所有饰品", "卖出全部饰品", "卖光饰品", "清空饰品", "一键卖饰品"})(market_handlers.sell_all_accessories)
    shop = filter.command("商店")(market_handlers.shop)
    buy_rod = filter.command("购买鱼竿")(market_handlers.buy_rod)
    buy_bait = filter.command("购买鱼饵")(market_handlers.buy_bait)
    market = filter.command("市场")(market_handlers.market)
    list_rod = filter.command("上架鱼竿")(market_handlers.list_rod)
    list_accessories = filter.command("上架饰品")(market_handlers.list_accessories)
    list_item = filter.command("上架道具")(market_handlers.list_item)
    buy_item = filter.command("购买")(market_handlers.buy_item)
    my_listings = filter.command("我的上架", alias={"上架列表", "我的商品", "我的挂单"})(market_handlers.my_listings)
    delist_item = filter.command("下架")(market_handlers.delist_item)

    # ==========================================================
    # Social Commands
    # ==========================================================
    ranking = filter.command("排行榜", alias={"phb"})(social_handlers.ranking)
    steal_fish = filter.command("偷鱼")(social_handlers.steal_fish)
    steal_with_dispel = filter.command("驱灵")(social_handlers.steal_with_dispel)
    view_titles = filter.command("查看称号", alias={"称号"})(social_handlers.view_titles)
    use_title = filter.command("使用称号")(social_handlers.use_title)
    view_achievements = filter.command("查看成就", alias={ "成就" })(social_handlers.view_achievements)
    tax_record = filter.command("税收记录")(social_handlers.tax_record)

    # ==========================================================
    # Gacha Commands
    # ==========================================================
    gacha = filter.command("抽卡", alias={"抽奖"})(gacha_handlers.gacha)
    ten_gacha = filter.command("十连")(gacha_handlers.ten_gacha)
    view_gacha_pool = filter.command("查看卡池")(gacha_handlers.view_gacha_pool)
    gacha_history = filter.command("抽卡记录")(gacha_handlers.gacha_history)
    wipe_bomb = filter.command("擦弹")(gacha_handlers.wipe_bomb)
    wipe_bomb_history = filter.command("擦弹记录", alias={"擦弹历史"})(gacha_handlers.wipe_bomb_history)

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

