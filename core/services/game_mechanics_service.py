import requests
import random
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor
from astrbot.api import logger

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractLogRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository
)
from ..domain.models import WipeBombLog
from ..utils import get_now

class GameMechanicsService:
    """封装特殊或独立的游戏机制"""

    def __init__(
        self,
        user_repo: AbstractUserRepository,
        log_repo: AbstractLogRepository,
        inventory_repo: AbstractInventoryRepository,
        item_template_repo: AbstractItemTemplateRepository,
        config: Dict[str, Any]
    ):
        self.user_repo = user_repo
        self.log_repo = log_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.config = config
        self.thread_pool = ThreadPoolExecutor(max_workers=5)

    def perform_wipe_bomb(self, user_id: str, contribution_amount: int) -> Dict[str, Any]:
        """
        处理“擦弹”的完整逻辑。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 1. 验证投入金额
        if contribution_amount <= 0:
            return {"success": False, "message": "投入金额必须大于0"}
        if not user.can_afford(contribution_amount):
            return {"success": False, "message": f"金币不足，当前拥有 {user.coins} 金币"}

        # 2. 检查每日次数限制
        wipe_bomb_config = self.config.get("wipe_bomb", {})
        max_attempts = wipe_bomb_config.get("max_attempts_per_day", 3)
        attempts_today = self.log_repo.get_wipe_bomb_log_count_today(user_id)
        if attempts_today >= max_attempts:
            return {"success": False, "message": f"你今天已经使用了{max_attempts}次擦弹，明天再来吧！"}

        # 3. 计算随机奖励倍数 (使用加权随机)
        ranges = wipe_bomb_config.get("reward_ranges", [])
        total_weight = sum(w for _, _, w in ranges)
        rand_val = random.uniform(0, total_weight)

        reward_multiplier = 0.0
        current_weight = 0
        for r_min, r_max, weight in ranges:
            current_weight += weight
            if rand_val <= current_weight:
                reward_multiplier = round(random.uniform(r_min, r_max), 1)
                break

        # 4. 计算最终金额并执行事务
        reward_amount = int(contribution_amount * reward_multiplier)
        profit = reward_amount - contribution_amount

        user.coins += profit
        self.user_repo.update(user)

        # 5. 记录日志
        log_entry = WipeBombLog(
            log_id=0, # DB自增
            user_id=user_id,
            contribution_amount=contribution_amount,
            reward_multiplier=reward_multiplier,
            reward_amount=reward_amount,
            timestamp=get_now()
        )
        self.log_repo.add_wipe_bomb_log(log_entry)

        # 上传非敏感数据到服务器
        # 在单独线程中异步上传数据
        def upload_data_async():
            upload_data = {
                "user_id": user_id,
                "contribution_amount": contribution_amount,
                "reward_multiplier": reward_multiplier,
                "reward_amount": reward_amount,
                "profit": profit,
                "timestamp": log_entry.timestamp.isoformat()
            }
            api_url = "http://veyu.me/api/record"
            try:
                response = requests.post(api_url, json=upload_data)
                if response.status_code != 200:
                    logger.info(f"上传数据失败: {response.text}")
            except Exception as e:
                logger.error(f"上传数据时发生错误: {e}")

        # 启动异步线程进行数据上传，不阻塞主流程
        self.thread_pool.submit(upload_data_async)


        return {
            "success": True,
            "contribution": contribution_amount,
            "multiplier": reward_multiplier,
            "reward": reward_amount,
            "profit": profit,
            "remaining_today": max_attempts - (attempts_today + 1)
        }

    def get_wipe_bomb_history(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        获取用户的擦弹历史记录。
        """
        logs = self.log_repo.get_wipe_bomb_logs(user_id, limit)
        return {
            "success": True,
            "logs": [
                {
                    "contribution": log.contribution_amount,
                    "multiplier": log.reward_multiplier,
                    "reward": log.reward_amount,
                    "timestamp": log.timestamp
                } for log in logs
            ]
        }

    def steal_fish(self, thief_id: str, victim_id: str) -> Dict[str, Any]:
        """
        处理“偷鱼”的逻辑。
        """
        if thief_id == victim_id:
            return {"success": False, "message": "不能偷自己的鱼！"}

        thief = self.user_repo.get_by_id(thief_id)
        if not thief:
            return {"success": False, "message": "偷窃者用户不存在"}

        victim = self.user_repo.get_by_id(victim_id)
        if not victim:
            return {"success": False, "message": "目标用户不存在"}

        # 1. 检查偷窃CD
        cooldown_seconds = self.config.get("steal", {}).get("cooldown_seconds", 14400) # 默认4小时
        now = get_now()
        if thief.last_steal_time and (now - thief.last_steal_time).total_seconds() < cooldown_seconds:
            remaining = int(cooldown_seconds - (now - thief.last_steal_time).total_seconds())
            return {"success": False, "message": f"偷鱼冷却中，请等待 {remaining // 60} 分钟后再试"}

        # 2. 检查受害者是否有鱼可偷
        victim_inventory = self.inventory_repo.get_fish_inventory(victim_id)
        if not victim_inventory:
            return {"success": False, "message": f"目标用户【{victim.nickname}】的鱼塘是空的！"}

        # 3. 随机选择一条鱼偷取
        stolen_fish_item = random.choice(victim_inventory)
        stolen_fish_template = self.item_template_repo.get_fish_by_id(stolen_fish_item.fish_id)

        if not stolen_fish_template:
            return {"success": False, "message": "发生内部错误，无法识别被偷的鱼"}

        # 4. 执行偷窃事务
        # 从受害者库存中移除一条鱼
        self.inventory_repo.update_fish_quantity(victim_id, stolen_fish_item.fish_id, delta=-1)
        # 向偷窃者库存中添加一条鱼
        self.inventory_repo.add_fish_to_inventory(thief_id, stolen_fish_item.fish_id, quantity=1)

        # 5. 更新偷窃者的CD时间
        thief.last_steal_time = now
        self.user_repo.update(thief)

        return {
            "success": True,
            "message": f"✅ 成功从【{victim.nickname}】的鱼塘里偷到了一条{stolen_fish_template.rarity}★【{stolen_fish_template.name}】！基础价值 {stolen_fish_template.base_value} 金币",
        }
