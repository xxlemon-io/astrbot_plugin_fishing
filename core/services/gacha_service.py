import random
from typing import Dict, Any

from astrbot.core.utils.pip_installer import logger
# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractGachaRepository,
    AbstractUserRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository,
    AbstractLogRepository,
    AbstractAchievementRepository
)
from ..domain.models import GachaPool, GachaPoolItem, GachaRecord
from ..utils import get_now


def _perform_single_weighted_draw(pool: GachaPool) -> GachaPoolItem:
    """执行一次加权随机抽奖。"""
    total_weight = sum(item.weight for item in pool.items)
    rand_val = random.uniform(0, total_weight)

    current_weight = 0
    for item in pool.items:
        current_weight += item.weight
        if rand_val <= current_weight:
            return item
    return None # 理论上不会发生


class GachaService:
    """封装与抽卡系统相关的业务逻辑"""

    def __init__(
        self,
        gacha_repo: AbstractGachaRepository,
        user_repo: AbstractUserRepository,
        inventory_repo: AbstractInventoryRepository,
        item_template_repo: AbstractItemTemplateRepository,
        log_repo: AbstractLogRepository,
        achievement_repo: AbstractAchievementRepository
    ):
        self.gacha_repo = gacha_repo
        self.user_repo = user_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.achievement_repo = achievement_repo
        self.log_repo = log_repo

    def get_all_pools(self) -> Dict[str, Any]:
        """提供查看所有卡池信息的功能。"""
        try:
            pools = self.gacha_repo.get_all_pools()
            logger.info(f"获取到 {len(pools)} 个卡池信息")
            return {"success": True, "pools": pools}
        except Exception as e:
            return {"success": False, "message": f"获取卡池信息失败: {str(e)}"}

    def get_pool_details(self, pool_id: int) -> Dict[str, Any]:
        """获取单个卡池的详细信息，包括奖品列表和概率。"""
        pool = self.gacha_repo.get_pool_by_id(pool_id)
        if not pool:
            return {"success": False, "message": "该卡池不存在"}

        total_weight = sum(item.weight for item in pool.items)
        if total_weight == 0:
            return {"success": True, "pool": pool, "probabilities": {}}

        probabilities = []
        for item in pool.items:
            probability = float(item.weight / total_weight)
            item_name = "未知物品"
            item_rarity = 1
            if item.item_type == "rod":
                rod = self.item_template_repo.get_rod_by_id(item.item_id)
                item_name = rod.name if rod else "未知鱼竿"
                item_rarity = rod.rarity if rod else 1
            elif item.item_type == "accessory":
                accessory = self.item_template_repo.get_accessory_by_id(item.item_id)
                item_name = accessory.name if accessory else "未知饰品"
                item_rarity = accessory.rarity if accessory else 1
            elif item.item_type == "bait":
                bait = self.item_template_repo.get_bait_by_id(item.item_id)
                item_name = bait.name if bait else "未知鱼饵"
                item_rarity = bait.rarity if bait else 1
            elif item.item_type == "coins":
                item_name = f"{item.quantity} 金币"
            elif item.item_type == "titles":
                item_name = self.item_template_repo.get_title_by_id(item.item_id).name

            probabilities.append({
                "item_type": item.item_type,
                "item_id": item.item_id,
                "item_name": item_name,
                "item_rarity": item_rarity if item.item_type != "titles" else 0,
                "weight": item.weight,
                "probability": 1.0 + round(probability, 4)
            })
        return {"success": True, "pool": pool, "probabilities": probabilities}

    def perform_draw(self, user_id: str, pool_id: int, num_draws: int = 1) -> Dict[str, Any]:
        """
        实现单抽和十连抽的核心逻辑。

        Args:
            user_id: 抽卡的用户ID
            pool_id: 卡池ID
            num_draws: 抽卡次数

        Returns:
            一个包含成功状态和抽卡结果的字典。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        pool = self.gacha_repo.get_pool_by_id(pool_id)
        if not pool or not pool.items:
            return {"success": False, "message": "卡池不存在或卡池为空"}

        # 计算费用：若配置了高级货币费用，则优先使用高级货币；否则使用金币
        use_premium_currency = (getattr(pool, "cost_premium_currency", 0) or 0) > 0
        total_premium_cost = (pool.cost_premium_currency or 0) * num_draws
        total_coin_cost = (pool.cost_coins or 0) * num_draws

        if use_premium_currency:
            if user.premium_currency < total_premium_cost:
                return {"success": False, "message": f"高级货币不足，需要 {total_premium_cost} 点高级货币"}
        else:
            if not user.can_afford(total_coin_cost):
                return {"success": False, "message": f"金币不足，需要 {total_coin_cost} 金币"}

        # 1. 执行抽卡
        draw_results = []
        for _ in range(num_draws):
            drawn_item = _perform_single_weighted_draw(pool)
            if drawn_item:
                draw_results.append(drawn_item)

        if not draw_results:
            return {"success": False, "message": "抽卡失败，请检查卡池配置"}

        # 2. 扣除费用
        if use_premium_currency:
            user.premium_currency -= total_premium_cost
        else:
            user.coins -= total_coin_cost
        self.user_repo.update(user)

        # 3. 发放奖励并记录日志
        granted_rewards = []
        for item in draw_results:
            self._grant_reward(user_id, item)
            # 将抽奖结果 => 转换为用户可见的奖励格式
            if item.item_type == "rod":
                get_rod = self.item_template_repo.get_rod_by_id(item.item_id)
                granted_rewards.append({
                    "type": "rod",
                    "id": item.item_id,
                    "name": get_rod.name,
                    "rarity": get_rod.rarity
                })
            elif item.item_type == "accessory":
                get_accessory = self.item_template_repo.get_accessory_by_id(item.item_id)
                granted_rewards.append({
                    "type": "accessory",
                    "id": item.item_id,
                    "name": get_accessory.name,
                    "rarity": get_accessory.rarity
                })
            elif item.item_type == "bait":
                get_bait = self.item_template_repo.get_bait_by_id(item.item_id)
                granted_rewards.append({
                    "type": "bait",
                    "id": item.item_id,
                    "name": get_bait.name,
                    "rarity": get_bait.rarity,
                    "quantity": item.quantity
                })
            elif item.item_type == "coins":
                granted_rewards.append({
                    "type": "coins",
                    "quantity": item.quantity
                })
            elif item.item_type == "titles":
                granted_rewards.append({
                    "type": "title",
                    "id": item.item_id,
                    "name": self.item_template_repo.get_title_by_id(item.item_id).name
                })

        return {"success": True, "results": granted_rewards}

    def _grant_reward(self, user_id: str, item: GachaPoolItem):
        """根据抽到的物品，为用户发放具体奖励并记录日志。"""
        item_name = "未知物品"
        item_rarity = 1
        template = None

        if item.item_type == "rod":
            self.inventory_repo.add_rod_instance(user_id, item.item_id, None) # 假设新获得的鱼竿耐久度是满的
            template = self.item_template_repo.get_rod_by_id(item.item_id)
        elif item.item_type == "accessory":
            self.inventory_repo.add_accessory_instance(user_id, item.item_id)
            template = self.item_template_repo.get_accessory_by_id(item.item_id)
        elif item.item_type == "bait":
            self.inventory_repo.update_bait_quantity(user_id, item.item_id, item.quantity)
            template = self.item_template_repo.get_bait_by_id(item.item_id)
        elif item.item_type == "coins":
            user = self.user_repo.get_by_id(user_id)
            user.coins += item.quantity
            self.user_repo.update(user)
            item_name = f"{item.quantity} 金币"
        elif item.item_type == "titles":
            # 注意：成就仓储负责授予称号
            self.achievement_repo.grant_title_to_user(user_id, item.item_id)
            template = self.item_template_repo.get_title_by_id(item.item_id)

        if template:
            item_name = template.name
            item_rarity = template.rarity if hasattr(template, "rarity") else 1

        # 记录日志
        log_entry = GachaRecord(
            record_id=0, # DB自增
            user_id=user_id,
            gacha_pool_id=item.gacha_pool_id,
            item_type=item.item_type,
            item_id=item.item_id,
            item_name=item_name,
            quantity=item.quantity,
            rarity=item_rarity,
            timestamp=get_now()
        )
        self.log_repo.add_gacha_record(log_entry)

    def get_user_gacha_history(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """提供查询抽卡历史记录的功能。"""
        records = self.log_repo.get_gacha_records(user_id, limit)
        return {"success": True, "records": records}
