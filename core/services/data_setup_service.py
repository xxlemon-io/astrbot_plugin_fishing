from ..repositories.abstract_repository import (
    AbstractItemTemplateRepository,
    AbstractGachaRepository,
)
from ..initial_data import (
    FISH_DATA,
    BAIT_DATA,
    ROD_DATA,
    ACCESSORY_DATA,
    TITLE_DATA,
    GACHA_POOL,
    ITEM_DATA,
)
from ..domain.models import Item
from astrbot.api import logger


class DataSetupService:
    """负责在首次启动时初始化游戏基础数据。"""

    def __init__(self, item_template_repo: AbstractItemTemplateRepository, gacha_repo: AbstractGachaRepository):
        """
        初始化数据设置服务。

        Args:
            item_template_repo: 物品模板仓储的实例，用于与数据库交互。
        """
        self.gacha_repo = gacha_repo
        self.item_template_repo = item_template_repo

    def setup_initial_data(self):
        """
        检查核心数据表是否为空，如果为空则进行数据填充。
        这是一个幂等操作（idempotent），可以安全地多次调用而不会重复插入数据。
        """
        try:
            existing_fish = self.item_template_repo.get_all_fish()
            if existing_fish:
                # print("数据库核心数据已存在，跳过初始化。")
                return
        except Exception as e:
            # 如果表不存在等数据库错误，也需要继续执行创建和插入
            logger.error(f"检查数据时发生错误 (可能是表不存在，将继续初始化): {e}")

        logger.info("检测到数据库为空或核心数据不完整，正在初始化游戏数据...")

        # 填充鱼类数据
        for fish in FISH_DATA:
            self.item_template_repo.add_fish_template({
                "name": fish[0],
                "description": fish[1],
                "rarity": fish[2],
                "base_value": fish[3],
                "min_weight": fish[4],
                "max_weight": fish[5],
                "icon_url": fish[6]
            })

        # 填充鱼饵数据
        for bait in BAIT_DATA:
            self.item_template_repo.add_bait_template({
                "name": bait[0],
                "description": bait[1],
                "rarity": bait[2],
                "effect_description": bait[3],
                "duration_minutes": bait[4],
                "cost": bait[5],
                "required_rod_rarity": bait[6]
            })

        # 填充鱼竿数据
        for rod in ROD_DATA:
            self.item_template_repo.add_rod_template({
                "name": rod[0],
                "description": rod[1],
                "rarity": rod[2],
                "source": rod[3],
                "purchase_cost": rod[4],
                "bonus_fish_quality_modifier": rod[5],
                "bonus_fish_quantity_modifier": rod[6],
                "bonus_rare_fish_chance": rod[7],
                "durability": rod[8],
                "icon_url": rod[9]
            })

        # 填充饰品数据
        for acc in ACCESSORY_DATA:
            self.item_template_repo.add_accessory_template({
                "name": acc[0],
                "description": acc[1],
                "rarity": acc[2],
                "slot_type": acc[3],
                "bonus_fish_quality_modifier": acc[4],
                "bonus_fish_quantity_modifier": acc[5],
                "bonus_rare_fish_chance": acc[6],
                "bonus_coin_modifier": acc[7],
                "other_bonus_description": acc[8],
                "icon_url": acc[9]
            })


        for title in TITLE_DATA:
            if hasattr(self.item_template_repo, "add_title_template"):
                self.item_template_repo.add_title_template({
                    "title_id": title[0],
                    "name": title[1],
                    "description": title[2],
                    "display_format": title[3]
                })

        for pool in GACHA_POOL:
            self.gacha_repo.add_pool_template(
                {
                    "pool_id": pool[0],
                    "name": pool[1],
                    "description": pool[2],
                    "cost_coins": pool[3],
                    "cost_premium_currency": pool[4],
                }
            )

        # 填充道具数据
        self.create_initial_items()

        # --- 填充抽卡池具体物品 ---
        # 检查是否已填充，避免重复
        if not self.gacha_repo.get_pool_items(1):
            self.gacha_repo.add_pool_item(1, {"item_type": "rod", "item_id": 4, "quantity": 1, "weight": 10}) # 星辰钓者
            self.gacha_repo.add_pool_item(1, {"item_type": "rod", "item_id": 5, "quantity": 1, "weight": 3}) # 海神之赐
            self.gacha_repo.add_pool_item(1, {"item_type": "rod", "item_id": 3, "quantity": 1, "weight": 30}) # 碳素纤维竿
            self.gacha_repo.add_pool_item(1, {"item_type": "coins", "item_id": 0, "quantity": 10000, "weight": 57})

        if not self.gacha_repo.get_pool_items(2):
            self.gacha_repo.add_pool_item(2, {"item_type": "accessory", "item_id": 4, "quantity": 1, "weight": 5}) # 海洋之心
            self.gacha_repo.add_pool_item(2, {"item_type": "accessory", "item_id": 3, "quantity": 1, "weight": 15}) # 丰收号角
            self.gacha_repo.add_pool_item(2, {"item_type": "coins", "item_id": 0, "quantity": 20000, "weight": 80})

        logger.info("核心游戏数据初始化完成。")

    def create_initial_items(self):
        """创建初始的道具"""
        existing_items = self.item_template_repo.get_all()
        existing_item_names = {item.name for item in existing_items}

        items_to_create = []
        for item_data in ITEM_DATA:
            if item_data[1] not in existing_item_names:
                items_to_create.append(
                    Item(
                        item_id=0,  # ID is auto-incrementing
                        name=item_data[1],
                        description=item_data[2],
                        rarity=item_data[3],
                        effect_description=item_data[4],
                        cost=item_data[5],
                        is_consumable=item_data[6],
                        icon_url=item_data[7],
                        effect_type=item_data[8],
                        effect_payload=item_data[9],
                    )
                )

        if items_to_create:
            logger.info(f"发现 {len(items_to_create)} 个新的道具，正在添加到数据库...")
            for item in items_to_create:
                self.item_template_repo.add(item)
            logger.info("新道具添加完成。")
        else:
            logger.info("没有发现新的道具需要添加。")

