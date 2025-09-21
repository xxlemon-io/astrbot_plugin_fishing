import os
import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve

from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.message.components import At
from astrbot.core.star.filter.permission import PermissionType

# ==========================================================
# 导入重构后的所有模块
# ==========================================================
# 仓储实现
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
# 服务
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
# 其他

from .core.database.migration import run_migrations
from .core.utils import get_now
from .draw.rank import draw_fishing_ranking
from .draw.help import draw_help_image
from .draw.state import draw_state_image, get_user_state_data
from .manager.server import create_app
from .utils import to_percentage, format_accessory_or_rod, safe_datetime_handler, _is_port_available, format_rarity_display, kill_processes_on_port


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
            logger.warning(f"无法使用 self.context.get_data_dir('{self.plugin_id}'), 将回退到旧的 'data/' 目录。请考虑升级 AstrBot 框架以获得更好的数据隔离。")
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
        # 已移除按配置文件注入区域配额的旧逻辑（on_load）

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

    # ===========基础与核心玩法==========

    @filter.command("注册")
    async def register_user(self, event: AstrMessageEvent):
        """注册用户命令"""
        user_id = self._get_effective_user_id(event)
        nickname = event.get_sender_name() if event.get_sender_name() is not None else user_id
        result = self.user_service.register(user_id, nickname)
        if result:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("钓鱼")
    async def fish(self, event: AstrMessageEvent):
        """钓鱼"""
        user_id = self._get_effective_user_id(event)
        user = self.user_repo.get_by_id(user_id)
        if not user:
            yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")
            return
        # 检查用户钓鱼CD
        lst_time = user.last_fishing_time
        # 检查是否装备了海洋之心饰品
        info = self.user_service.get_user_current_accessory(user_id)
        if info["success"] is False:
            yield event.plain_result(f"❌ 获取用户饰品信息失败：{info['message']}")
            return
        equipped_accessory = info.get("accessory")
        cooldown_seconds = self.game_config["fishing"]["cooldown_seconds"]
        if equipped_accessory and equipped_accessory.get("name") == "海洋之心":
            # 如果装备了海洋之心，CD时间减半
            cooldown_seconds = self.game_config["fishing"]["cooldown_seconds"] / 2
            # logger.info(f"用户 {user_id} 装备了海洋之心，钓鱼CD时间减半。")
        # 修复时区问题
        now = get_now()
        if lst_time and lst_time.tzinfo is None and now.tzinfo is not None:
            # 如果 lst_time 没有时区而 now 有时区，移除 now 的时区信息
            now = now.replace(tzinfo=None)
        elif lst_time and lst_time.tzinfo is not None and now.tzinfo is None:
            # 如果 lst_time 有时区而 now 没有时区，将 now 转换为有时区
            now = now.replace(tzinfo=lst_time.tzinfo)
        if lst_time and (now - lst_time).total_seconds() < cooldown_seconds:
            wait_time = cooldown_seconds - (now - lst_time).total_seconds()
            yield event.plain_result(f"⏳ 您还需要等待 {int(wait_time)} 秒才能再次钓鱼。")
            return
        result = self.fishing_service.go_fish(user_id)
        if result:
            if result["success"]:
                # 获取当前区域的钓鱼消耗
                zone = self.inventory_repo.get_zone_by_id(user.fishing_zone_id)
                fishing_cost = zone.fishing_cost if zone else 10
                
                message = f"🎣 恭喜你钓到了：{result['fish']['name']}\n✨品质：{'★' * result['fish']['rarity']} \n⚖️重量：{result['fish']['weight']} 克\n💰价值：{result['fish']['value']} 金币\n💸消耗：{fishing_cost} 金币/次"
                
                # 添加装备损坏消息
                if "equipment_broken_messages" in result:
                    for broken_msg in result["equipment_broken_messages"]:
                        message += f"\n{broken_msg}"
                
                yield event.plain_result(message)
            else:
                # 即使钓鱼失败，也显示消耗的金币
                zone = self.inventory_repo.get_zone_by_id(user.fishing_zone_id)
                fishing_cost = zone.fishing_cost if zone else 10
                message = f"{result['message']}\n💸消耗：{fishing_cost} 金币/次"
                yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("签到")
    async def sign_in(self, event: AstrMessageEvent):
        """签到"""
        user_id = self._get_effective_user_id(event)
        result = self.user_service.daily_sign_in(user_id)
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 签到失败：{result['message']}")

    @filter.command("自动钓鱼")
    async def auto_fish(self, event: AstrMessageEvent):
        """自动钓鱼"""
        user_id = self._get_effective_user_id(event)
        result = self.fishing_service.toggle_auto_fishing(user_id)
        yield event.plain_result(result["message"])

    @filter.command("钓鱼记录", alias={"钓鱼日志", "钓鱼历史"})
    async def fishing_log(self, event: AstrMessageEvent):
        """查看钓鱼记录"""
        user_id = self._get_effective_user_id(event)
        result = self.fishing_service.get_user_fish_log(user_id)
        if result:
            if result["success"]:
                records = result["records"]
                if not records:
                    yield event.plain_result("❌ 您还没有钓鱼记录。")
                    return
                message = "【📜 钓鱼记录】：\n"
                for record in records:
                    message += (f" - {record['fish_name']} ({'★' * record['fish_rarity']})\n"
                                f" - ⚖️重量: {record['fish_weight']} 克 - 💰价值: {record['fish_value']} 金币\n"
                                f" - 🔧装备： {record['accessory']} & {record['rod']} | 🎣鱼饵: {record['bait']}\n"
                                f" - 钓鱼时间: {safe_datetime_handler(record['timestamp'])}\n")
                yield event.plain_result(message)
            else:
                yield event.plain_result(f"❌ 获取钓鱼记录失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    # ===========背包与资产管理==========

    @filter.command("状态", alias={"我的状态"})
    async def state(self, event: AstrMessageEvent):
        """查看用户状态"""
        user_id = self._get_effective_user_id(event)
        
        # 调用新的数据获取函数
        user_data = get_user_state_data(self.user_repo, self.inventory_repo, self.item_template_repo, self.log_repo, self.buff_repo, self.game_config, user_id)
        
        if not user_data:
            yield event.plain_result('❌ 用户不存在，请先发送"注册"来开始游戏')
            return
        # 生成状态图像
        image = await draw_state_image(user_data, self.data_dir)
        # 保存图像到临时文件
        image_path = os.path.join(self.tmp_dir, "user_status.png")
        image.save(image_path)
        yield event.image_result(image_path)

    @filter.command("背包", alias={"查看背包", "我的背包"})
    async def user_backpack(self, event: AstrMessageEvent):
        """查看用户背包"""
        user_id = self._get_effective_user_id(event)
        user = self.user_repo.get_by_id(user_id)
        if user:
            # 导入绘制函数
            from .draw.backpack import draw_backpack_image, get_user_backpack_data
            
            # 获取用户背包数据
            backpack_data = get_user_backpack_data(self.inventory_service, user_id)
            
            # 设置用户昵称
            backpack_data['nickname'] = user.nickname or user_id
            
            # 生成背包图像
            image = await draw_backpack_image(backpack_data, self.data_dir)
            # 保存图像到临时文件
            image_path = os.path.join(self.tmp_dir, "user_backpack.png")
            image.save(image_path)
            yield event.image_result(image_path)
        else:
            yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")
    @filter.command("鱼塘")
    async def pond(self, event: AstrMessageEvent):
        """查看用户鱼塘内的鱼"""
        user_id = self._get_effective_user_id(event)
        pond_fish = self.inventory_service.get_user_fish_pond(user_id)
        if pond_fish:
            fishes = pond_fish["fishes"]
            # 把fishes按稀有度分组
            fished_by_rarity = {}
            for fish in fishes:
                rarity = fish.get("rarity", "未知")
                if rarity not in fished_by_rarity:
                    fished_by_rarity[rarity] = []
                fished_by_rarity[rarity].append(fish)
            # 构造输出信息
            message = "【🐠 鱼塘】：\n"
            for rarity in sorted(fished_by_rarity.keys(), reverse=True):
                fish_list = fished_by_rarity[rarity]
                if fish_list:
                    message += f"\n {format_rarity_display(rarity)} 稀有度 {rarity}：\n"
                    for fish in fish_list:
                        message += f"  - {fish['name']} x  {fish['quantity']} （{fish['base_value']}金币 / 个） \n"
            message += f"\n🐟 总鱼数：{pond_fish['stats']['total_count']} 条\n"
            message += f"💰 总价值：{pond_fish['stats']['total_value']} 金币\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("🐟 您的鱼塘是空的，快去钓鱼吧！")

    @filter.command("鱼塘容量")
    async def pond_capacity(self, event: AstrMessageEvent):
        """查看用户鱼塘容量"""
        user_id = self._get_effective_user_id(event)
        pond_capacity = self.inventory_service.get_user_fish_pond_capacity(user_id)
        if pond_capacity["success"]:
            message = f"🐠 您的鱼塘容量为 {pond_capacity['current_fish_count']} / {pond_capacity['fish_pond_capacity']} 条鱼。"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("升级鱼塘", alias={"鱼塘升级"})
    async def upgrade_pond(self, event: AstrMessageEvent):
        """升级鱼塘容量"""
        user_id = self._get_effective_user_id(event)
        result = self.inventory_service.upgrade_fish_pond(user_id)
        if result["success"]:
            yield event.plain_result(f"🐠 鱼塘升级成功！新容量为 {result['new_capacity']} 条鱼。")
        else:
            yield event.plain_result(f"❌ 升级失败：{result['message']}")

    @filter.command("鱼竿")
    async def rod(self, event: AstrMessageEvent):
        """查看用户鱼竿信息"""
        user_id = self._get_effective_user_id(event)
        rod_info = self.inventory_service.get_user_rod_inventory(user_id)
        if rod_info and rod_info["rods"]:
            # 构造输出信息,附带emoji
            message = "【🎣 鱼竿】：\n"
            for rod in rod_info["rods"]:
                message += format_accessory_or_rod(rod)
                if rod.get("bonus_rare_fish_chance", 1) != 1 and rod.get("bonus_fish_weight", 1.0) != 1.0:
                    message += f"   - 钓上鱼鱼类几率加成: {to_percentage(rod['bonus_rare_fish_chance'])}\n"
                message += f"   -精炼等级: {rod.get('refine_level', 1)}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("🎣 您还没有鱼竿，快去商店购买或抽奖获得吧！")

    @filter.command("精炼鱼竿", alias={"鱼竿精炼"})
    async def refine_rod(self, event: AstrMessageEvent):
        """精炼鱼竿"""
        user_id = self._get_effective_user_id(event)
        rod_info = self.inventory_service.get_user_rod_inventory(user_id)
        if not rod_info or not rod_info["rods"]:
            yield event.plain_result("❌ 您还没有鱼竿，请先购买或抽奖获得。")
            return
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要精炼的鱼竿 ID，例如：/精炼鱼竿 12")
            return
        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        result = self.inventory_service.refine(user_id, int(rod_instance_id), "rod")
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 精炼鱼竿失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("鱼饵")
    async def bait(self, event: AstrMessageEvent):
        """查看用户鱼饵信息"""
        user_id = self._get_effective_user_id(event)
        bait_info = self.inventory_service.get_user_bait_inventory(user_id)
        if bait_info and bait_info["baits"]:
            # 构造输出信息,附带emoji
            message = "【🐟 鱼饵】：\n"
            for bait in bait_info["baits"]:
                message += f" - {bait['name']} x {bait['quantity']} (稀有度: {format_rarity_display(bait['rarity'])})\n"
                message += f"   - ID: {bait['bait_id']}\n"
                if bait["duration_minutes"] > 0:
                    message += f"   - 持续时间: {bait['duration_minutes']} 分钟\n"
                if bait["effect_description"]:
                    message += f"   - 效果: {bait['effect_description']}\n"
                message += "\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("🐟 您还没有鱼饵，快去商店购买或抽奖获得吧！")

    @filter.command("道具", alias={"我的道具", "查看道具"})
    async def items(self, event: AstrMessageEvent):
        """查看用户道具信息（文本版）"""
        user_id = self._get_effective_user_id(event)
        item_info = self.inventory_service.get_user_item_inventory(user_id)
        if item_info and item_info.get("items"):
            message = "【📦 道具】：\n"
            for it in item_info["items"]:
                consumable_text = "消耗品" if it.get("is_consumable") else "非消耗"
                message += f" - {it['name']} x {it['quantity']} (稀有度: {format_rarity_display(it['rarity'])}，{consumable_text})\n"
                message += f"   - ID: {it['item_id']}\n"
                if it.get("effect_description"):
                    message += f"   - 效果: {it['effect_description']}\n"
                message += "\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("📦 您还没有道具。")

    @filter.command("使用道具", alias={"使用"})
    async def use_item(self, event: AstrMessageEvent):
        """使用一个道具"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要使用的道具 ID，例如：/使用道具 1")
            return
        
        item_id_str = args[1]
        if not item_id_str.isdigit():
            yield event.plain_result("❌ 道具 ID 必须是数字。")
            return
        
        item_id = int(item_id_str)
        
        quantity = 1
        if len(args) > 2 and args[2].isdigit():
            quantity = int(args[2])
            if quantity <= 0:
                yield event.plain_result("❌ 数量必须是正整数。")
                return

        # 批量使用道具，设置显示上限避免消息过长
        DETAIL_DISPLAY_LIMIT = 5  # 最多显示5个道具的详细效果
        success_count = 0
        failed_count = 0
        last_error_message = ""
        success_messages = []
        
        for _ in range(quantity):
            result = self.inventory_service.use_item(user_id, item_id)
            
            if result["success"]:
                success_count += 1
                success_messages.append(result["message"])
            else:
                failed_count += 1
                last_error_message = result["message"]
                # 如果失败，则停止使用后续的道具
                break

        # 发送汇总消息
        if success_count > 0 and failed_count == 0:
            if quantity == 1:
                # 单个道具使用时，显示具体的道具效果消息
                yield event.plain_result(f"✅ {success_messages[0]}")
            else:
                # 多个道具使用时，显示汇总 + 详细效果（有上限）
                message = f"✅ 成功使用了 {success_count} 个道具！\n\n"
                
                # 显示详细效果（最多显示前N个）
                display_count = min(success_count, DETAIL_DISPLAY_LIMIT)
                message += "📋 使用效果：\n"
                for i in range(display_count):
                    message += f"{i+1}. {success_messages[i]}\n"
                
                # 如果还有更多未显示的
                if success_count > DETAIL_DISPLAY_LIMIT:
                    remaining = success_count - DETAIL_DISPLAY_LIMIT
                    message += f"... 还有 {remaining} 个道具产生了相同效果"
                
                yield event.plain_result(message)
        elif success_count > 0 and failed_count > 0:
            message = f"⚠️ 成功使用了 {success_count} 个道具，{failed_count} 个失败：{last_error_message}\n\n"
            
            # 显示成功的详细效果
            if success_count > 0:
                display_count = min(success_count, DETAIL_DISPLAY_LIMIT)
                message += "📋 成功的效果：\n"
                for i in range(display_count):
                    message += f"{i+1}. {success_messages[i]}\n"
                    
                if success_count > DETAIL_DISPLAY_LIMIT:
                    remaining = success_count - DETAIL_DISPLAY_LIMIT
                    message += f"... 还有 {remaining} 个道具产生了相同效果"
            
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 使用道具失败：{last_error_message}")

    @filter.command("卖道具", alias={"出售道具", "卖出道具"})
    async def sell_item(self, event: AstrMessageEvent):
        """卖出道具：/卖道具 <ID> [数量]，数量缺省为1"""
        user_id = self._get_effective_user_id(event)
        parts = event.message_str.strip().split()
        if len(parts) < 2:
            yield event.plain_result("❌ 用法：/卖道具 <道具ID> [数量]")
            return
        if not parts[1].isdigit():
            yield event.plain_result("❌ 道具ID必须是数字")
            return
        item_id = int(parts[1])
        qty = 1
        if len(parts) >= 3 and parts[2].isdigit():
            qty = int(parts[2])
        result = self.inventory_service.sell_item(user_id, item_id, qty)
        if result.get("success"):
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(result.get("message", "操作失败"))

    @filter.command("饰品")
    async def accessories(self, event: AstrMessageEvent):
        """查看用户饰品信息"""
        user_id = self._get_effective_user_id(event)
        accessories_info = self.inventory_service.get_user_accessory_inventory(user_id)
        if accessories_info and accessories_info["accessories"]:
            # 构造输出信息,附带emoji
            message = "【💍 饰品】：\n"
            for accessory in accessories_info["accessories"]:
                message += format_accessory_or_rod(accessory)
                message += f"   -精炼等级: {accessory.get('refine_level', 1)}\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("💍 您还没有饰品，快去商店购买或抽奖获得吧！")

    @filter.command("精炼饰品", alias={"饰品精炼"})
    async def refine_accessory(self, event: AstrMessageEvent):
        """精炼饰品"""
        user_id = self._get_effective_user_id(event)
        accessories_info = self.inventory_service.get_user_accessory_inventory(user_id)
        if not accessories_info or not accessories_info["accessories"]:
            yield event.plain_result("❌ 您还没有饰品，请先购买或抽奖获得。")
            return
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要精炼的饰品 ID，例如：/精炼饰品 15")
            return
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        result = self.inventory_service.refine(user_id, int(accessory_instance_id), "accessory")
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 精炼饰品失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("精炼帮助", alias={"精炼说明", "精炼"})
    async def refine_help(self, event: AstrMessageEvent):
        """精炼系统帮助（当前版本）"""
        help_message = """🔨 精炼系统指南（当前版本）

═══════════════════════════════════
📖 核心规则
═══════════════════════════════════

• 精炼对象：鱼竿、饰品（同模板之间精炼）
• 等级范围：1级 → 10级（目前的满级）
• 消耗条件：同模板材料 + 金币
• 每次只升1级：精N → 精N+1
• 材料选择：优先使用"未装备、精炼等级最低"的同模板实例；永不使用正在装备的作为材料

成功：
• 目标等级+1，消耗1件材料与对应金币

失败（两种）：
• 普通失败：装备本体不变，但会消耗1件材料与对应金币
• 毁坏失败（高等级概率触发）：消耗1件材料与对应金币，并摧毁本体装备

═══════════════════════════════════
🌟 稀有度与费用/成功率
═══════════════════════════════════

🎲 成功率（关键档位）：
• 1-4星：前期成功率高，后期逐步下降（更易满精）
• 5星：6→10级约为 60%、50%、45%、40%、35%
• 6星：6→10级约为 50%、45%、40%、35%、30%
• 7星及以上：挑战性高，6→10级约为 40%、35%、30%、20%、15%-20%

提示：成功率按"目标新等级"计算（例如精2→精3，用精3的成功率）。

═══════════════════════════════════
⚡ 属性成长与加成
═══════════════════════════════════

• 1-3星：≈+15%/级
• 4星：≈+12%/级
• 5星：≈+8%/级
• 6星：≈+5%/级
• 7星+：≈+3%/级

═══════════════════════════════════
💰 精炼收益（系统回收价）
═══════════════════════════════════

• 售价 = 基础价(按稀有度) × 精炼等级乘数
• 基础价（示例）：1★=100，2★=500，3★=2000，4★=5000，5★=10000
• 精炼乘数（示例）：1→10级：1.0, 1.6, 3.0, 6.0, 12.0, 25.0, 55.0, 125.0, 280.0, 660.0
• 设计目标：收益随等级近指数增长，高精炼装备可覆盖成本并获得显著利润
• 批量出售会逐件按该规则计价，跳过正在装备的物品
• 玩家市场价格由卖家自定，不受该公式限制

═══════════════════════════════════
🏆 耐久度（仅鱼竿）
═══════════════════════════════════

• 每次钓鱼：鱼竿耐久 -1，降至0自动卸下
• 精炼成功：耐久恢复至当前最大值
• 每升1级：最大耐久度 ×1.5（累计）
• 神器奖励：5星及以上鱼竿精炼到10级 → 获得"无限耐久"（∞）
• 饰品无耐久度，不受上述规则影响

═══════════════════════════════════
📝 命令用法
═══════════════════════════════════

• /精炼鱼竿 [鱼竿实例ID]
• /精炼饰品 [饰品实例ID]
• 需要至少两件同模板装备（目标 + 材料）
• 查看背包以确认实例ID：/背包、/鱼竿、/饰品

"""

        yield event.plain_result(help_message)

    @filter.command("锁定鱼竿", alias={"鱼竿锁定"})
    async def lock_rod(self, event: AstrMessageEvent):
        """锁定鱼竿，防止被精炼、卖出、上架"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要锁定的鱼竿 ID，例如：/锁定鱼竿 15")
            return
        
        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        
        result = self.inventory_service.lock_rod(user_id, int(rod_instance_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 锁定失败：{result['message']}")

    @filter.command("解锁鱼竿", alias={"鱼竿解锁"})
    async def unlock_rod(self, event: AstrMessageEvent):
        """解锁鱼竿，允许正常操作"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要解锁的鱼竿 ID，例如：/解锁鱼竿 15")
            return
        
        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        
        result = self.inventory_service.unlock_rod(user_id, int(rod_instance_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 解锁失败：{result['message']}")

    @filter.command("锁定饰品", alias={"饰品锁定"})
    async def lock_accessory(self, event: AstrMessageEvent):
        """锁定饰品，防止被精炼、卖出、上架"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要锁定的饰品 ID，例如：/锁定饰品 15")
            return
        
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        
        result = self.inventory_service.lock_accessory(user_id, int(accessory_instance_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 锁定失败：{result['message']}")

    @filter.command("解锁饰品", alias={"饰品解锁"})
    async def unlock_accessory(self, event: AstrMessageEvent):
        """解锁饰品，允许正常操作"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要解锁的饰品 ID，例如：/解锁饰品 15")
            return
        
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        
        result = self.inventory_service.unlock_accessory(user_id, int(accessory_instance_id))
        if result["success"]:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(f"❌ 解锁失败：{result['message']}")

    @filter.command("使用鱼竿")
    async def use_rod(self, event: AstrMessageEvent):
        """使用鱼竿"""
        user_id = self._get_effective_user_id(event)
        rod_info = self.inventory_service.get_user_rod_inventory(user_id)
        if not rod_info or not rod_info["rods"]:
            yield event.plain_result("❌ 您还没有鱼竿，请先购买或抽奖获得。")
            return
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要使用的鱼竿 ID，例如：/使用鱼竿 12")
            return

        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        result = self.inventory_service.equip_item(user_id, int(rod_instance_id), "rod")
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 使用鱼竿失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("使用鱼饵")
    async def use_bait(self, event: AstrMessageEvent):
        """使用鱼饵"""
        user_id = self._get_effective_user_id(event)
        bait_info = self.inventory_service.get_user_bait_inventory(user_id)
        if not bait_info or not bait_info["baits"]:
            yield event.plain_result("❌ 您还没有鱼饵，请先购买或抽奖获得。")
            return
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要使用的鱼饵 ID，例如：/使用鱼饵 13")
            return
        bait_instance_id = args[1]
        if not bait_instance_id.isdigit():
            yield event.plain_result("❌ 鱼饵 ID 必须是数字，请检查后重试。")
            return
        result = self.inventory_service.use_bait(user_id, int(bait_instance_id))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 使用鱼饵失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("使用饰品")
    async def use_accessories(self, event: AstrMessageEvent):
        """使用饰品"""
        user_id = self._get_effective_user_id(event)
        accessories_info = self.inventory_service.get_user_accessory_inventory(user_id)
        if not accessories_info or not accessories_info["accessories"]:
            yield event.plain_result("❌ 您还没有饰品，请先购买或抽奖获得。")
            return
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要使用的饰品 ID，例如：/使用饰品 15")
            return
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        result = self.inventory_service.equip_item(user_id, int(accessory_instance_id), "accessory")
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 使用饰品失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("金币")
    async def coins(self, event: AstrMessageEvent):
        """查看用户金币信息"""
        user_id = self._get_effective_user_id(event)
        user = self.user_repo.get_by_id(user_id)
        if user:
            yield event.plain_result(f"💰 您的金币余额：{user.coins} 金币")
        else:
            yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")

    @filter.command("高级货币", alias={"钻石", "星石"})
    async def premium(self, event: AstrMessageEvent):
        """查看用户高级货币信息"""
        user_id = self._get_effective_user_id(event)
        user = self.user_repo.get_by_id(user_id)
        if user:
            yield event.plain_result(f"💎 您的高级货币余额：{user.premium_currency}")
        else:
            yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")

    # ===========商店与市场==========

    @filter.command("全部卖出", alias={"全部出售", "卖出全部", "出售全部", "卖光", "清空鱼", "一键卖出"})
    async def sell_all(self, event: AstrMessageEvent):
        """卖出用户所有鱼"""
        user_id = self._get_effective_user_id(event)
        result = self.inventory_service.sell_all_fish(user_id)
        if result:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("保留卖出", alias={"保留出售", "卖出保留", "出售保留", "留一卖出", "卖鱼留一"})
    async def sell_keep(self, event: AstrMessageEvent):
        """卖出用户鱼，但保留每种鱼一条"""
        user_id = self._get_effective_user_id(event)
        result = self.inventory_service.sell_all_fish(user_id, keep_one=True)
        if result:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("砸锅卖铁", alias={"破产", "清仓", "一键清空", "全部卖出装备", "卖光所有"})
    async def sell_everything(self, event: AstrMessageEvent):
        """砸锅卖铁：出售所有未锁定且未装备的鱼竿、饰品和全部鱼类"""
        user_id = self._get_effective_user_id(event)
        result = self.inventory_service.sell_everything_except_locked(user_id)
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 砸锅卖铁失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("出售稀有度", alias={"按稀有度出售", "稀有度出售", "卖稀有度", "出售星级", "按星级出售"})
    async def sell_by_rarity(self, event: AstrMessageEvent):
        """按稀有度出售鱼"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要出售的稀有度，例如：/出售稀有度 3")
            return
        rarity = args[1]
        if not rarity.isdigit() or int(rarity) < 1 or int(rarity) > 5:
            yield event.plain_result("❌ 稀有度必须是1到5之间的数字，请检查后重试。")
            return
        result = self.inventory_service.sell_fish_by_rarity(user_id, int(rarity))
        if result:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("出售鱼竿", alias={"卖出鱼竿", "卖鱼竿", "卖掉鱼竿"})
    async def sell_rod(self, event: AstrMessageEvent):
        """出售鱼竿"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要出售的鱼竿 ID，例如：/出售鱼竿 12")
            return
        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        result = self.inventory_service.sell_rod(user_id, int(rod_instance_id))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 出售鱼竿失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    # 批量删除用户鱼竿
    @filter.command("出售所有鱼竿", alias={"出售全部鱼竿", "卖出所有鱼竿", "卖出全部鱼竿", "卖光鱼竿", "清空鱼竿", "一键卖鱼竿"})
    async def sell_all_rods(self, event: AstrMessageEvent):
        """出售用户所有鱼竿"""
        user_id = self._get_effective_user_id(event)
        result = self.inventory_service.sell_all_rods(user_id)
        if result:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("出售饰品", alias={"卖出饰品", "卖饰品", "卖掉饰品"})
    async def sell_accessories(self, event: AstrMessageEvent):
        """出售饰品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要出售的饰品 ID，例如：/出售饰品 15")
            return
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        result = self.inventory_service.sell_accessory(user_id, int(accessory_instance_id))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 出售饰品失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("出售所有饰品", alias={"出售全部饰品", "卖出所有饰品", "卖出全部饰品", "卖光饰品", "清空饰品", "一键卖饰品"})
    async def sell_all_accessories(self, event: AstrMessageEvent):
        """出售用户所有饰品"""
        user_id = self._get_effective_user_id(event)
        result = self.inventory_service.sell_all_accessories(user_id)
        if result:
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("商店")
    async def shop(self, event: AstrMessageEvent):
        """查看商店"""
        result = self.shop_service.get_shop_listings()
        if result:
            message = "【🛒 商店】\n\n"
            if result["baits"]:
                message += "【🐟 鱼饵】:\n"
                for bait in result["baits"]:
                    message += f" - {bait.name} (ID: {bait.bait_id}) - 价格: {bait.cost} 金币\n - 描述：{bait.description}\n\n"
            else:
                message += "🐟 商店中没有鱼饵可供购买。\n\n"
            if result["rods"]:
                message += "\n【🎣 鱼竿】:\n"
                for rod in result["rods"]:
                    message += f" - {rod.name} (ID: {rod.rod_id}) - 价格: {rod.purchase_cost} 金币\n"
                    if rod.bonus_fish_quality_modifier != 1.0:
                        message += f"   - 质量加成⬆️: {to_percentage(rod.bonus_fish_quality_modifier)}\n"
                    if rod.bonus_fish_quantity_modifier != 1.0:
                        message += f"   - 数量加成⬆️: {to_percentage(rod.bonus_fish_quantity_modifier)}\n"
                    if rod.bonus_rare_fish_chance != 0.0:
                        message += f"   - 钓鱼加成⬆️: {to_percentage(rod.bonus_rare_fish_chance)}\n"
                    message += "\n"
            else:
                message += "🎣 商店中没有鱼竿可供购买。\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("购买鱼竿")
    async def buy_rod(self, event: AstrMessageEvent):
        """购买鱼竿"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要购买的鱼竿 ID，例如：/购买鱼竿 12")
            return
        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        result = self.shop_service.buy_item(user_id, "rod", int(rod_instance_id))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 购买鱼竿失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("购买鱼饵")
    async def buy_bait(self, event: AstrMessageEvent):
        """购买鱼饵"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要购买的鱼饵 ID，例如：/购买鱼饵 13")
            return
        bait_instance_id = args[1]
        if not bait_instance_id.isdigit():
            yield event.plain_result("❌ 鱼饵 ID 必须是数字，请检查后重试。")
            return
        quantity = 1  # 默认购买数量为1
        if len(args) == 3:
            quantity = args[2]
            if not quantity.isdigit() or int(quantity) <= 0:
                yield event.plain_result("❌ 购买数量必须是正整数，请检查后重试。")
                return
        result = self.shop_service.buy_item(user_id, "bait", int(bait_instance_id), int(quantity))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 购买鱼饵失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("市场")
    async def market(self, event: AstrMessageEvent):
        """查看市场"""
        result = self.market_service.get_market_listings()
        if result["success"]:
            message = "【🛒 市场】\n\n"
            if result["rods"]:
                message += "【🎣 鱼竿】:\n"
                for rod in result["rods"]:
                    message += f" - {rod['item_name']} 精{rod['refine_level']} (ID: {rod['market_id']}) - 价格: {rod['price']} 金币\n"
                    message += f" - 售卖人： {rod['seller_nickname']}\n\n"
            else:
                message += "🎣 市场中没有鱼竿可供购买。\n\n"
            if result["accessories"]:
                message += "【💍 饰品】:\n"
                for accessory in result["accessories"]:
                    message += f" - {accessory['item_name']} 精{accessory['refine_level']} (ID: {accessory['market_id']}) - 价格: {accessory['price']} 金币\n"
                    message += f" - 售卖人： {accessory['seller_nickname']}\n\n"
            else:
                message += "💍 市场中没有饰品可供购买。\n\n"
            if result["items"]:
                message += "【🎁 道具】:\n"
                for item in result["items"]:
                    message += f" - {item['item_name']} (ID: {item['market_id']}) - 价格: {item['price']} 金币\n"
                    message += f" - 售卖人： {item['seller_nickname']}\n\n"
            else:
                message += "🎁 市场中没有道具可供购买。\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 出错啦！{result['message']}")


    @filter.command("上架鱼竿")
    async def list_rod(self, event: AstrMessageEvent):
        """上架鱼竿到市场"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定要上架的鱼竿 ID和价格，例如：/上架鱼竿 12 1000")
            return
        rod_instance_id = args[1]
        if not rod_instance_id.isdigit():
            yield event.plain_result("❌ 鱼竿 ID 必须是数字，请检查后重试。")
            return
        price = args[2]
        if not price.isdigit() or int(price) <= 0:
            yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
            return
        result = self.market_service.put_item_on_sale(user_id, "rod", int(rod_instance_id), int(price))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 上架鱼竿失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("上架饰品")
    async def list_accessories(self, event: AstrMessageEvent):
        """上架饰品到市场"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定要上架的饰品 ID和价格，例如：/上架饰品 15 1000")
            return
        accessory_instance_id = args[1]
        if not accessory_instance_id.isdigit():
            yield event.plain_result("❌ 饰品 ID 必须是数字，请检查后重试。")
            return
        price = args[2]
        if not price.isdigit() or int(price) <= 0:
            yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
            return
        result = self.market_service.put_item_on_sale(user_id, "accessory", int(accessory_instance_id), int(price))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 上架饰品失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("上架道具")
    async def list_item(self, event: AstrMessageEvent):
        """上架道具到市场"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定要上架的道具 ID和价格，例如：/上架道具 1 1000")
            return
        item_id = args[1]
        if not item_id.isdigit():
            yield event.plain_result("❌ 道具 ID 必须是数字，请检查后重试。")
            return
        price = args[2]
        if not price.isdigit() or int(price) <= 0:
            yield event.plain_result("❌ 上架价格必须是正整数，请检查后重试。")
            return
        result = self.market_service.put_item_on_sale(user_id, "item", int(item_id), int(price))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 上架道具失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("购买")
    async def buy_item(self, event: AstrMessageEvent):
        """购买市场上的物品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要购买的物品 ID，例如：/购买 12")
            return
        item_instance_id = args[1]
        if not item_instance_id.isdigit():
            yield event.plain_result("❌ 物品 ID 必须是数字，请检查后重试。")
            return
        result = self.market_service.buy_market_item(user_id, int(item_instance_id))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 购买失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("我的上架", alias={"上架列表", "我的商品"})
    async def my_listings(self, event: AstrMessageEvent):
        """查看我在市场上架的商品"""
        user_id = self._get_effective_user_id(event)
        result = self.market_service.get_user_listings(user_id)
        if result["success"]:
            listings = result["listings"]
            if not listings:
                yield event.plain_result("📦 您还没有在市场上架任何商品。")
                return
            
            message = f"【🛒 我的上架商品】共 {result['count']} 件\n\n"
            for listing in listings:
                message += f"🆔 ID: {listing.market_id}\n"
                message += f"📦 {listing.item_name}"
                if listing.refine_level > 1:
                    message += f" 精{listing.refine_level}"
                message += f"\n💰 价格: {listing.price} 金币\n"
                message += f"📅 上架时间: {listing.listed_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            message += "💡 使用「下架 ID」命令下架指定商品"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 查询失败：{result['message']}")

    @filter.command("下架")
    async def delist_item(self, event: AstrMessageEvent):
        """下架市场上的商品"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要下架的商品 ID，例如：/下架 12\n💡 使用「我的上架」命令查看您的商品列表")
            return
        market_id = args[1]
        if not market_id.isdigit():
            yield event.plain_result("❌ 商品 ID 必须是数字，请检查后重试。")
            return
        market_id = int(market_id)
        result = self.market_service.delist_item(user_id, market_id)
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 下架失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    # ===========抽卡与概率玩法==========
    @filter.command("抽卡", alias={"抽奖"})
    async def gacha(self, event: AstrMessageEvent):
        """抽卡"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            # 展示所有的抽奖池信息并显示帮助
            pools = self.gacha_service.get_all_pools()
            if not pools:
                yield event.plain_result("❌ 当前没有可用的抽奖池。")
                return
            message = "【🎰 抽奖池列表】\n\n"
            for pool in pools.get("pools", []):
                cost_text = f"💰 金币 {pool['cost_coins']} / 次"
                if pool['cost_premium_currency']:
                    cost_text = f"💎 高级货币 {pool['cost_premium_currency']} / 次"
                message += f"ID: {pool['gacha_pool_id']} - {pool['name']} - {pool['description']}\n {cost_text}\n\n"
            # 添加卡池详细信息
            message += "【📋 卡池详情】使用「查看卡池 ID」命令查看详细物品概率\n"
            message += "【🎲 抽卡命令】使用「抽卡 ID」命令选择抽卡池进行单次抽卡\n"
            message += "【🎯 十连命令】使用「十连 ID」命令进行十连抽卡"
            yield event.plain_result(message)
            return
        pool_id = args[1]
        if not pool_id.isdigit():
            yield event.plain_result("❌ 抽奖池 ID 必须是数字，请检查后重试。")
            return
        pool_id = int(pool_id)
        result = self.gacha_service.perform_draw(user_id, pool_id, num_draws=1)
        if result:
            if result["success"]:
                items = result.get("results", [])
                message = f"🎉 抽卡成功！您抽到了 {len(items)} 件物品：\n"
                for item in items:
                    # 构造输出信息
                    if item.get("type") == "coins":
                        # 金币类型的物品
                        message += f"⭐ {item['quantity']} 金币！\n"
                    else:
                        message += f"{'⭐' * item.get('rarity', 1)} {item['name']}\n"
                yield event.plain_result(message)
            else:
                yield event.plain_result(f"❌ 抽卡失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("十连")
    async def ten_gacha(self, event: AstrMessageEvent):
        """十连抽卡"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要进行十连抽卡的抽奖池 ID，例如：/十连 1")
            return
        pool_id = args[1]
        if not pool_id.isdigit():
            yield event.plain_result("❌ 抽奖池 ID 必须是数字，请检查后重试。")
            return
        pool_id = int(pool_id)
        result = self.gacha_service.perform_draw(user_id, pool_id, num_draws=10)
        if result:
            if result["success"]:
                items = result.get("results", [])
                message = f"🎉 十连抽卡成功！您抽到了 {len(items)} 件物品：\n"
                for item in items:
                    # 构造输出信息
                    if item.get("type") == "coins":
                        # 金币类型的物品
                        message += f"⭐ {item['quantity']} 金币！\n"
                    else:
                        message += f"{'⭐' * item.get('rarity', 1)} {item['name']}\n"
                yield event.plain_result(message)
            else:
                yield event.plain_result(f"❌ 抽卡失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("查看卡池")
    async def view_gacha_pool(self, event: AstrMessageEvent):
        """查看当前卡池"""
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要查看的卡池 ID，例如：/查看卡池 1")
            return
        pool_id = args[1]
        if not pool_id.isdigit():
            yield event.plain_result("❌ 卡池 ID 必须是数字，请检查后重试。")
            return
        pool_id = int(pool_id)
        result = self.gacha_service.get_pool_details(pool_id)
        if result:
            if result["success"]:
                pool = result.get("pool", {})
                message = "【🎰 卡池详情】\n\n"
                message += f"ID: {pool['gacha_pool_id']} - {pool['name']}\n"
                message += f"描述: {pool['description']}\n"
                # 限时开放信息展示
                try:
                    if pool['is_limited_time']:
                        open_until = pool['open_until']
                        if open_until:
                            # 格式化为 YYYY/MM/DD HH:MM
                            display_time = open_until.replace('T', ' ').replace('-', '/')
                            if len(display_time) > 16:
                                display_time = display_time[:16]
                            message += f"限时开放 至: {display_time}\n"
                except Exception:
                    pass
                if pool['cost_premium_currency']:
                    message += f"花费: {pool['cost_premium_currency']} 高级货币 / 次\n\n"
                else:
                    message += f"花费: {pool['cost_coins']} 金币 / 次\n\n"
                message += "【📋 物品概率】\n"

                if result["probabilities"]:
                    for item in result["probabilities"]:
                        message += f" - {'⭐' * item.get('item_rarity', 0)} {item['item_name']} (概率: {to_percentage(item['probability'])})\n"
                yield event.plain_result(message)
            else:
                yield event.plain_result(f"❌ 查看卡池失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("抽卡记录")
    async def gacha_history(self, event: AstrMessageEvent):
        """查看抽卡记录"""
        user_id = self._get_effective_user_id(event)
        result = self.gacha_service.get_user_gacha_history(user_id)
        if result:
            if result["success"]:
                history = result.get("records", [])
                if not history:
                    yield event.plain_result("📜 您还没有抽卡记录。")
                    return
                message = "【📜 抽卡记录】\n\n"
                for record in history:
                    message += f"物品名称: {record['item_name']} (稀有度: {'⭐' * record['rarity']})\n"
                    message += f"时间: {safe_datetime_handler(record['timestamp'])}\n\n"
                yield event.plain_result(message)
            else:
                yield event.plain_result(f"❌ 查看抽卡记录失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("擦弹")
    async def wipe_bomb(self, event: AstrMessageEvent):
        """擦弹功能"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("💸 请指定要擦弹的数量 ID，例如：/擦弹 123456789")
            return
        contribution_amount = args[1]
        if contribution_amount in ['allin', 'halfin', '梭哈', '梭一半']:
            # 查询用户当前金币数量
            user = self.user_repo.get_by_id(user_id)
            if user:
                coins = user.coins
            else:
                yield event.plain_result("❌ 您还没有注册，请先使用 /注册 命令注册。")
                return
            if contribution_amount == 'allin' or contribution_amount == '梭哈':
                contribution_amount = coins
            elif contribution_amount == 'halfin' or contribution_amount == '梭一半':
                contribution_amount = coins // 2
            contribution_amount = str(contribution_amount)
        # 判断是否为int或数字字符串
        if not contribution_amount.isdigit():
            yield event.plain_result("❌ 擦弹数量必须是数字，请检查后重试。")
            return
        result = self.game_mechanics_service.perform_wipe_bomb(user_id, int(contribution_amount))
        if result:
            if result["success"]:
                message = ""
                contribution = result["contribution"]
                multiplier = result["multiplier"]
                reward = result["reward"]
                profit = result["profit"]
                remaining_today = result["remaining_today"]
                
                # 格式化倍率，保留两位小数
                multiplier_formatted = f"{multiplier:.2f}"

                if multiplier >= 3:
                    message += f"🎰 大成功！你投入 {contribution} 金币，获得了 {multiplier_formatted} 倍奖励！\n 💰 奖励金额：{reward} 金币（盈利：+ {profit}）\n"
                elif multiplier >= 1:
                    message += f"🎲 你投入 {contribution} 金币，获得了 {multiplier_formatted} 倍奖励！\n 💰 奖励金额：{reward} 金币（盈利：+ {profit}）\n"
                else:
                    message += f"💥 你投入 {contribution} 金币，获得了 {multiplier_formatted} 倍奖励！\n 💰 奖励金额：{reward} 金币（亏损：- {abs(profit)})\n"
                message += f"剩余擦弹次数：{remaining_today} 次\n"
                yield event.plain_result(message)
            else:
                yield event.plain_result(f"⚠️ 擦弹失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("擦弹记录", alias={"擦弹历史"})
    async def wipe_bomb_history(self, event: AstrMessageEvent):
        """查看擦弹记录"""
        user_id = self._get_effective_user_id(event)
        result = self.game_mechanics_service.get_wipe_bomb_history(user_id)
        if result:
            if result["success"]:
                history = result.get("logs", [])
                if not history:
                    yield event.plain_result("📜 您还没有擦弹记录。")
                    return
                message = "【📜 擦弹记录】\n\n"
                for record in history:
                    # 添加一点emoji
                    message += f"⏱️ 时间: {safe_datetime_handler(record['timestamp'])}\n"
                    message += f"💸 投入: {record['contribution']} 金币, 🎁 奖励: {record['reward']} 金币\n"
                    # 计算盈亏
                    profit = record["reward"] - record["contribution"]
                    profit_text = f"盈利: +{profit}" if profit >= 0 else f"亏损: {profit}"
                    profit_emoji = "📈" if profit >= 0 else "📉"

                    if record["multiplier"] >= 3:
                        message += f"🔥 倍率: {record['multiplier']} ({profit_emoji} {profit_text})\n\n"
                    elif record["multiplier"] >= 1:
                        message += f"✨ 倍率: {record['multiplier']} ({profit_emoji} {profit_text})\n\n"
                    else:
                        message += f"💔 倍率: {record['multiplier']} ({profit_emoji} {profit_text})\n\n"
                yield event.plain_result(message)
            else:
                yield event.plain_result(f"❌ 查看擦弹记录失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    # ===========社交==========
    @filter.command("排行榜", alias={"phb"})
    async def ranking(self, event: AstrMessageEvent):
        """查看排行榜"""
        user_data = self.user_service.get_leaderboard_data().get("leaderboard", [])
        if not user_data:
            yield event.plain_result("❌ 当前没有排行榜数据。")
            return
        for user in user_data:
            if user["title"] is None:
                user["title"] = "无称号"
            if user["accessory"] is None:
                user["accessory"] = "无饰品"
            if user["fishing_rod"] is None:
                user["fishing_rod"] = "无鱼竿"
        # logger.info(f"用户数据: {user_data}")
        output_path = os.path.join(self.tmp_dir, "fishing_ranking.png")
        draw_fishing_ranking(user_data, output_path=output_path)
        yield event.image_result(output_path)

    @filter.command("偷鱼")
    async def steal_fish(self, event: AstrMessageEvent):
        """偷鱼功能"""
        user_id = self._get_effective_user_id(event)
        message_obj = event.message_obj
        target_id = None
        if hasattr(message_obj, "message"):
            # 检查消息中是否有At对象
            for comp in message_obj.message:
                if isinstance(comp, At):
                    target_id = comp.qq
                    break
        if target_id is None:
            yield event.plain_result("请在消息中@要偷鱼的用户")
            return
        if int(target_id) == int(user_id):
            yield event.plain_result("不能偷自己的鱼哦！")
            return
        result = self.game_mechanics_service.steal_fish(user_id, target_id)
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 偷鱼失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("查看称号", alias={"称号"})
    async def view_titles(self, event: AstrMessageEvent):
        """查看用户称号"""
        user_id = self._get_effective_user_id(event)
        titles = self.user_service.get_user_titles(user_id).get("titles", [])
        if titles:
            message = "【🏅 您的称号】\n"
            for title in titles:
                message += f"- {title['name']} (ID: {title['title_id']})\n- 描述: {title['description']}\n\n"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 您还没有任何称号，快去完成成就或参与活动获取吧！")


    @filter.command("使用称号")
    async def use_title(self, event: AstrMessageEvent):
        """使用称号"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定要使用的称号 ID，例如：/使用称号 1")
            return
        title_id = args[1]
        if not title_id.isdigit():
            yield event.plain_result("❌ 称号 ID 必须是数字，请检查后重试。")
            return
        result = self.user_service.use_title(user_id, int(title_id))
        if result:
            if result["success"]:
                yield event.plain_result(result["message"])
            else:
                yield event.plain_result(f"❌ 使用称号失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("查看成就", alias={ "成就" })
    async def view_achievements(self, event: AstrMessageEvent):
        """查看用户成就"""
        user_id = self._get_effective_user_id(event)
        achievements = self.achievement_service.get_user_achievements(user_id).get("achievements", [])
        if achievements:
            message = "【🏆 您的成就】\n"
            for achievement in achievements:
                message += f"- {achievement['name']} (ID: {achievement['id']})\n"
                message += f"  描述: {achievement['description']}\n"
                if achievement.get("completed_at"):
                    message += f"  完成时间: {safe_datetime_handler(achievement['completed_at'])}\n"
                else:
                    message += "  进度: {}/{}\n".format(achievement["progress"], achievement["target"])
            message += "请继续努力完成更多成就！"
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 您还没有任何成就，快去完成任务或参与活动获取吧！")

    @filter.command("税收记录")
    async def tax_record(self, event: AstrMessageEvent):
        """查看税收记录"""
        user_id = self._get_effective_user_id(event)
        result = self.user_service.get_tax_record(user_id)
        if result:
            if result["success"]:
                records = result.get("records", [])
                if not records:
                    yield event.plain_result("📜 您还没有税收记录。")
                    return
                message = "【📜 税收记录】\n\n"
                for record in records:
                    message += f"⏱️ 时间: {safe_datetime_handler(record['timestamp'])}\n"
                    message += f"💰 金额: {record['amount']} 金币\n"
                    message += f"📊 描述: {record['tax_type']}\n\n"
                yield event.plain_result(message)
            else:
                yield event.plain_result(f"❌ 查看税收记录失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.command("钓鱼区域", alias={"区域"})
    async def fishing_area(self, event: AstrMessageEvent):
        """查看当前钓鱼区域"""
        user_id = self._get_effective_user_id(event)
        args = event.message_str.split(" ")
        if len(args) < 2:
            result = self.fishing_service.get_user_fishing_zones(user_id)
            if result:
                if result["success"]:
                    zones = result.get("zones", [])
                    message = f"【🌊 钓鱼区域】\n"
                    for zone in zones:
                        # 区域状态标识
                        status_icons = []
                        if zone['whether_in_use']:
                            status_icons.append("✅")
                        if not zone['is_active']:
                            status_icons.append("🚫")
                        if zone.get('requires_pass'):
                            status_icons.append("🔑")
                        
                        status_text = " ".join(status_icons) if status_icons else ""
                        
                        message += f"区域名称: {zone['name']} (ID: {zone['zone_id']}) {status_text}\n"
                        message += f"描述: {zone['description']}\n"
                        message += f"💰 钓鱼消耗: {zone.get('fishing_cost', 10)} 金币/次\n"
                        
                        if zone.get('requires_pass'):
                            required_item_name = zone.get('required_item_name', '通行证')
                            message += f"🔑 需要 {required_item_name} 才能进入\n"
                        
                        # 显示限时信息（只有当有具体时间限制时才显示）
                        if zone.get('available_from') or zone.get('available_until'):
                            message += "⏰ 开放时间: "
                            if zone.get('available_from') and zone.get('available_until'):
                                # 有开始和结束时间
                                from_time = zone['available_from'].strftime('%Y-%m-%d %H:%M')
                                until_time = zone['available_until'].strftime('%Y-%m-%d %H:%M')
                                message += f"{from_time} 至 {until_time}\n"
                            elif zone.get('available_from'):
                                # 只有开始时间
                                from_time = zone['available_from'].strftime('%Y-%m-%d %H:%M')
                                message += f"{from_time} 开始\n"
                            elif zone.get('available_until'):
                                # 只有结束时间
                                until_time = zone['available_until'].strftime('%Y-%m-%d %H:%M')
                                message += f"至 {until_time} 结束\n"
                        
                        if zone['zone_id'] >= 2:
                            message += f"剩余稀有鱼类数量: {zone['daily_rare_fish_quota'] - zone['rare_fish_caught_today']}\n"
                        message += "\n"
                    
                    message += "使用「/钓鱼区域 ID」命令切换钓鱼区域。\n"
                    yield event.plain_result(message)
                else:
                    yield event.plain_result(f"❌ 查看钓鱼区域失败：{result['message']}")
            else:
                yield event.plain_result("❌ 出错啦！请稍后再试。")
            return
        zone_id = args[1]
        if not zone_id.isdigit():
            yield event.plain_result("❌ 钓鱼区域 ID 必须是数字，请检查后重试。")
            return
        zone_id = int(zone_id)
        
        # 动态获取所有有效的区域ID
        all_zones = self.fishing_zone_service.get_all_zones()
        valid_zone_ids = [zone['id'] for zone in all_zones]
        
        if zone_id not in valid_zone_ids:
            yield event.plain_result(f"❌ 无效的钓鱼区域 ID。有效ID为: {', '.join(map(str, valid_zone_ids))}")
            yield event.plain_result("💡 请使用「/钓鱼区域 <ID>」命令指定区域ID")
            return
        
        # 切换用户的钓鱼区域
        result = self.fishing_service.set_user_fishing_zone(user_id, zone_id)
        yield event.plain_result(result["message"] if result else "❌ 出错啦！请稍后再试。")

    @filter.command("钓鱼帮助", alias={"钓鱼菜单", "菜单"})
    async def fishing_help(self, event: AstrMessageEvent):
        """显示钓鱼插件帮助信息"""
        image = draw_help_image()
        output_path = os.path.join(self.tmp_dir, "fishing_help.png")
        image.save(output_path)
        yield event.image_result(output_path)

    @filter.command("鱼类图鉴")
    async def fish_pokedex(self, event: AstrMessageEvent):
        """查看鱼类图鉴"""
        user_id = self._get_effective_user_id(event)
        result = self.fishing_service.get_user_pokedex(user_id)

        if result:
            if result["success"]:
                pokedex = result.get("pokedex", [])
                if not pokedex:
                    yield event.plain_result("❌ 您还没有捕捉到任何鱼类，快去钓鱼吧！")
                    return

                message = "【🐟 🌊 鱼类图鉴 📖 🎣】\n"
                message += f"🏆 解锁进度：{to_percentage(result['unlocked_percentage'])}\n"
                message += f"📊 收集情况：{result['unlocked_fish_count']} / {result['total_fish_count']} 种\n"

                for fish in pokedex:
                    rarity = fish["rarity"]

                    message += f" - {fish['name']} ({'✨' * rarity})\n"
                    message += f"💎 价值：{fish['value']} 金币\n"
                    message += f"🕰️ 首次捕获：{safe_datetime_handler(fish['first_caught_time'])}\n"
                    message += f"📜 描述：{fish['description']}\n"

                if len(message) <= 500:
                    yield event.plain_result(message)
                    return

                text_chunk_size = 1000  # 每个Plain文本块的最大字数
                node_chunk_size = 4  # 每个Node中最多包含的Plain文本块数量
                text_chunks = [message[i:i + text_chunk_size] for i in
                               range(0, len(message), text_chunk_size)]

                if not text_chunks:
                    yield event.plain_result("❌ 内容为空，无法发送。")
                    return

                grouped_chunks = [text_chunks[i:i + node_chunk_size] for i in
                                  range(0, len(text_chunks), node_chunk_size)]

                from astrbot.api.message_components import Node, Plain
                nodes_to_send = []
                for i, group in enumerate(grouped_chunks):
                    plain_components = [Plain(text=chunk) for chunk in group]

                    node = Node(
                        uin=event.get_self_id(),
                        name=f"鱼类图鉴 - 第 {i + 1} 页",
                        content=plain_components
                    )
                    nodes_to_send.append(node)

                try:
                    yield event.chain_result(nodes_to_send)
                except Exception as e:
                    yield event.plain_result(f"❌ 发送转发消息失败：{e}")

            else:
                yield event.plain_result(f"❌ 查看鱼类图鉴失败：{result['message']}")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")
    # ===========管理后台==========

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("修改金币")
    async def modify_coins(self, event: AstrMessageEvent):
        """修改用户金币"""
        user_id = event.get_sender_id()
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定要修改的用户 ID 和金币数量，例如：/修改金币 123456789 1000")
            return
        target_user_id = args[1]
        if not target_user_id.isdigit():
            yield event.plain_result("❌ 用户 ID 必须是数字，请检查后重试。")
            return
        coins = args[2]
        if not coins.isdigit():
            yield event.plain_result("❌ 金币数量必须是数字，请检查后重试。")
            return
        result = self.user_service.modify_user_coins(target_user_id, int(coins))
        if result:
            yield event.plain_result(f"✅ 成功修改用户 {target_user_id} 的金币数量为 {coins} 金币")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("修改高级货币")
    async def modify_premium(self, event: AstrMessageEvent):
        """修改用户高级货币"""
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定用户 ID 和高级货币数量，例如：/修改高级货币 123456789 100")
            return
        target_user_id = args[1]
        if not target_user_id.isdigit():
            yield event.plain_result("❌ 用户 ID 必须是数字，请检查后重试。")
            return
        premium = args[2]
        if not premium.isdigit():
            yield event.plain_result("❌ 高级货币数量必须是数字，请检查后重试。")
            return
        user = self.user_repo.get_by_id(target_user_id)
        if not user:
            yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
            return
        user.premium_currency = int(premium)
        self.user_repo.update(user)
        yield event.plain_result(f"✅ 成功修改用户 {target_user_id} 的高级货币为 {premium}")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("奖励高级货币")
    async def reward_premium(self, event: AstrMessageEvent):
        """奖励用户高级货币"""
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定用户 ID 和高级货币数量，例如：/奖励高级货币 123456789 100")
            return
        target_user_id = args[1]
        if not target_user_id.isdigit():
            yield event.plain_result("❌ 用户 ID 必须是数字，请检查后重试。")
            return
        premium = args[2]
        if not premium.isdigit():
            yield event.plain_result("❌ 高级货币数量必须是数字，请检查后重试。")
            return
        user = self.user_repo.get_by_id(target_user_id)
        if not user:
            yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
            return
        user.premium_currency += int(premium)
        self.user_repo.update(user)
        yield event.plain_result(f"✅ 成功给用户 {target_user_id} 奖励 {premium} 高级货币")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("扣除高级货币")
    async def deduct_premium(self, event: AstrMessageEvent):
        """扣除用户高级货币"""
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定用户 ID 和高级货币数量，例如：/扣除高级货币 123456789 100")
            return
        target_user_id = args[1]
        if not target_user_id.isdigit():
            yield event.plain_result("❌ 用户 ID 必须是数字，请检查后重试。")
            return
        premium = args[2]
        if not premium.isdigit():
            yield event.plain_result("❌ 高级货币数量必须是数字，请检查后重试。")
            return
        user = self.user_repo.get_by_id(target_user_id)
        if not user:
            yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
            return
        if int(premium) > user.premium_currency:
            yield event.plain_result("❌ 扣除的高级货币不能超过用户当前拥有数量")
            return
        user.premium_currency -= int(premium)
        self.user_repo.update(user)
        yield event.plain_result(f"✅ 成功扣除用户 {target_user_id} 的 {premium} 高级货币")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体奖励金币")
    async def reward_all_coins(self, event: AstrMessageEvent):
        """给所有注册用户发放金币"""
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定奖励的金币数量，例如：/全体奖励金币 1000")
            return
        amount = args[1]
        if not amount.isdigit() or int(amount) <= 0:
            yield event.plain_result("❌ 奖励数量必须是正整数，请检查后重试。")
            return
        amount_int = int(amount)
        user_ids = self.user_repo.get_all_user_ids()
        if not user_ids:
            yield event.plain_result("❌ 当前没有注册用户。")
            return
        updated = 0
        for uid in user_ids:
            user = self.user_repo.get_by_id(uid)
            if not user:
                continue
            user.coins += amount_int
            self.user_repo.update(user)
            updated += 1
        yield event.plain_result(f"✅ 已向 {updated} 位用户每人发放 {amount_int} 金币")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体奖励高级货币")
    async def reward_all_premium(self, event: AstrMessageEvent):
        """给所有注册用户发放高级货币"""
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定奖励的高级货币数量，例如：/全体奖励高级货币 100")
            return
        amount = args[1]
        if not amount.isdigit() or int(amount) <= 0:
            yield event.plain_result("❌ 奖励数量必须是正整数，请检查后重试。")
            return
        amount_int = int(amount)
        user_ids = self.user_repo.get_all_user_ids()
        if not user_ids:
            yield event.plain_result("❌ 当前没有注册用户。")
            return
        updated = 0
        for uid in user_ids:
            user = self.user_repo.get_by_id(uid)
            if not user:
                continue
            user.premium_currency += amount_int
            self.user_repo.update(user)
            updated += 1
        yield event.plain_result(f"✅ 已向 {updated} 位用户每人发放 {amount_int} 高级货币")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体扣除金币")
    async def deduct_all_coins(self, event: AstrMessageEvent):
        """从所有注册用户扣除金币（不低于0）"""
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定扣除的金币数量，例如：/全体扣除金币 1000")
            return
        amount = args[1]
        if not amount.isdigit() or int(amount) <= 0:
            yield event.plain_result("❌ 扣除数量必须是正整数，请检查后重试。")
            return
        amount_int = int(amount)
        user_ids = self.user_repo.get_all_user_ids()
        if not user_ids:
            yield event.plain_result("❌ 当前没有注册用户。")
            return
        affected = 0
        total_deducted = 0
        for uid in user_ids:
            user = self.user_repo.get_by_id(uid)
            if not user:
                continue
            if user.coins <= 0:
                continue
            deduct = amount_int if user.coins >= amount_int else user.coins
            if deduct <= 0:
                continue
            user.coins -= deduct
            self.user_repo.update(user)
            affected += 1
            total_deducted += deduct
        yield event.plain_result(f"✅ 已从 {affected} 位用户总计扣除 {total_deducted} 金币（每人至多 {amount_int}）")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("全体扣除高级货币")
    async def deduct_all_premium(self, event: AstrMessageEvent):
        """从所有注册用户扣除高级货币（不低于0）"""
        args = event.message_str.split(" ")
        if len(args) < 2:
            yield event.plain_result("❌ 请指定扣除的高级货币数量，例如：/全体扣除高级货币 100")
            return
        amount = args[1]
        if not amount.isdigit() or int(amount) <= 0:
            yield event.plain_result("❌ 扣除数量必须是正整数，请检查后重试。")
            return
        amount_int = int(amount)
        user_ids = self.user_repo.get_all_user_ids()
        if not user_ids:
            yield event.plain_result("❌ 当前没有注册用户。")
            return
        affected = 0
        total_deducted = 0
        for uid in user_ids:
            user = self.user_repo.get_by_id(uid)
            if not user:
                continue
            if user.premium_currency <= 0:
                continue
            deduct = amount_int if user.premium_currency >= amount_int else user.premium_currency
            if deduct <= 0:
                continue
            user.premium_currency -= deduct
            self.user_repo.update(user)
            affected += 1
            total_deducted += deduct
        yield event.plain_result(f"✅ 已从 {affected} 位用户总计扣除 {total_deducted} 高级货币（每人至多 {amount_int}）")
    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("奖励金币")
    async def reward_coins(self, event: AstrMessageEvent):
        """奖励用户金币"""
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定要奖励的用户 ID 和金币数量，例如：/奖励金币 123456789 1000")
            return
        target_user_id = args[1]
        if not target_user_id.isdigit():
            yield event.plain_result("❌ 用户 ID 必须是数字，请检查后重试。")
            return
        coins = args[2]
        if not coins.isdigit():
            yield event.plain_result("❌ 金币数量必须是数字，请检查后重试。")
            return
        current_coins = self.user_service.get_user_currency(target_user_id)
        if current_coins is None:
            yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
            return
        result = self.user_service.modify_user_coins(target_user_id, int(current_coins.get('coins') + int(coins)))
        if result:
            yield event.plain_result(f"✅ 成功给用户 {target_user_id} 奖励 {coins} 金币")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("扣除金币")
    async def deduct_coins(self, event: AstrMessageEvent):
        """扣除用户金币"""
        args = event.message_str.split(" ")
        if len(args) < 3:
            yield event.plain_result("❌ 请指定要扣除的用户 ID 和金币数量，例如：/扣除金币 123456789 1000")
            return
        target_user_id = args[1]
        if not target_user_id.isdigit():
            yield event.plain_result("❌ 用户 ID 必须是数字，请检查后重试。")
            return
        coins = args[2]
        if not coins.isdigit():
            yield event.plain_result("❌ 金币数量必须是数字，请检查后重试。")
            return
        current_coins = self.user_service.get_user_currency(target_user_id)
        if current_coins is None:
            yield event.plain_result("❌ 用户不存在或未注册，请检查后重试。")
            return
        if int(coins) > current_coins.get('coins'):
            yield event.plain_result("❌ 扣除的金币数量不能超过用户当前拥有的金币数量")
            return
        result = self.user_service.modify_user_coins(target_user_id, int(current_coins.get('coins') - int(coins)))
        if result:
            yield event.plain_result(f"✅ 成功扣除用户 {target_user_id} 的 {coins} 金币")
        else:
            yield event.plain_result("❌ 出错啦！请稍后再试。")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("开启钓鱼后台管理")
    async def start_admin(self, event: AstrMessageEvent):
        if self.web_admin_task and not self.web_admin_task.done():
            yield event.plain_result("❌ 钓鱼后台管理已经在运行中")
            return
        yield event.plain_result("🔄 正在启动钓鱼插件Web管理后台...")

        if not await _is_port_available(self.port):
            yield event.plain_result(f"❌ 端口 {self.port} 已被占用，请更换端口后重试")
            return

        try:
            services_to_inject = {
                "item_template_service": self.item_template_service,
                "user_service": self.user_service,
                "market_service": self.market_service,
                "fishing_zone_service": self.fishing_zone_service,
            }
            app = create_app(
                secret_key=self.secret_key,
                services=services_to_inject
            )
            config = Config()
            config.bind = [f"0.0.0.0:{self.port}"]
            self.web_admin_task = asyncio.create_task(serve(app, config))

            # 等待服务启动
            for i in range(10):
                if await self._check_port_active():
                    break
                await asyncio.sleep(1)
            else:
                raise Exception("⌛ 启动超时，请检查防火墙设置")

            await asyncio.sleep(1)  # 等待服务启动

            yield event.plain_result(f"✅ 钓鱼后台已启动！\n🔗请访问 http://localhost:{self.port}/admin\n🔑 密钥请到配置文件中查看\n\n⚠️ 重要提示：\n• 如需公网访问，请自行配置端口转发和防火墙规则\n• 确保端口 {self.port} 已开放并映射到公网IP\n• 建议使用反向代理（如Nginx）增强安全性")
        except Exception as e:
            logger.error(f"启动后台失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 启动后台失败: {e}")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("关闭钓鱼后台管理")
    async def stop_admin(self, event: AstrMessageEvent):
        """关闭钓鱼后台管理"""
        if not hasattr(self, "web_admin_task") or not self.web_admin_task or self.web_admin_task.done():
            yield event.plain_result("❌ 钓鱼后台管理没有在运行中")
            return

        try:
            # 1. 请求取消任务
            self.web_admin_task.cancel()
            # 2. 等待任务实际被取消
            await self.web_admin_task
        except asyncio.CancelledError:
            # 3. 捕获CancelledError，这是成功关闭的标志
            logger.info("钓鱼插件Web管理后台已成功关闭")
            yield event.plain_result("✅ 钓鱼后台已关闭")
        except Exception as e:
            # 4. 捕获其他可能的意外错误
            logger.error(f"关闭钓鱼后台管理时发生意外错误: {e}", exc_info=True)
            yield event.plain_result(f"❌ 关闭钓鱼后台管理失败: {e}")

    async def _check_port_active(self):
        """验证端口是否实际已激活"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", self.port),
                timeout=1
            )
            writer.close()
            return True
        except:  # noqa: E722
            return False

    async def terminate(self):
        """插件被卸载/停用时调用"""
        logger.info("钓鱼插件正在终止...")
        self.fishing_service.stop_auto_fishing_task()
        self.achievement_service.stop_achievement_check_task()
        if self.web_admin_task:
            self.web_admin_task.cancel()
        logger.info("钓鱼插件已成功终止。")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("同步道具", alias={"管理员 同步道具"})
    async def sync_items_from_initial_data(self, event: AstrMessageEvent):
        """从 initial_data.py 同步道具数据到数据库。"""
        try:
            self.data_setup_service.create_initial_items()
            yield event.plain_result(
                '✅ 成功执行初始道具同步操作。\n请检查后台或使用 /道具 命令确认数据。'
            )
        except Exception as e:
            logger.error(f"执行 sync_items_from_initial_data 命令时出错: {e}", exc_info=True)
            yield event.plain_result(f"❌ 操作失败，请查看后台日志。错误: {e}")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("代理上线")
    async def impersonate_start(self, event: AstrMessageEvent):
        """管理员开始扮演一名用户。"""
        admin_id = event.get_sender_id()
        args = event.message_str.split(" ")
        if len(args) < 2:
            # 如果已经在线，则显示当前状态
            if admin_id in self.impersonation_map:
                target_user_id = self.impersonation_map[admin_id]
                target_user = self.user_repo.get_by_id(target_user_id)
                nickname = target_user.nickname if target_user else '未知用户'
                yield event.plain_result(f"您当前正在代理用户: {nickname} ({target_user_id})")
            else:
                yield event.plain_result("用法: /代理上线 <目标用户ID>")
            return

        target_user_id = args[1]
        if not target_user_id.isdigit():
            yield event.plain_result("❌ 目标用户ID必须是数字。")
            return

        target_user = self.user_repo.get_by_id(target_user_id)
        if not target_user:
            yield event.plain_result("❌ 目标用户不存在。")
            return

        self.impersonation_map[admin_id] = target_user_id
        nickname = target_user.nickname
        yield event.plain_result(f"✅ 您已成功代理用户: {nickname} ({target_user_id})。\n现在您发送的所有游戏指令都将以该用户的身份执行。\n使用 /代理下线 结束代理。")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("代理下线")
    async def impersonate_stop(self, event: AstrMessageEvent):
        """管理员结束扮演用户。"""
        admin_id = event.get_sender_id()
        if admin_id in self.impersonation_map:
            del self.impersonation_map[admin_id]
            yield event.plain_result("✅ 您已成功结束代理。")
        else:
            yield event.plain_result("❌ 您当前没有在代理任何用户。")

