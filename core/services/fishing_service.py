import random
import threading
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from astrbot.api import logger

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository,
    AbstractLogRepository
)
from ..domain.models import FishingRecord, User
from ..utils import get_now


class FishingService:
    """封装核心的钓鱼动作及后台任务"""

    def __init__(
        self,
        user_repo: AbstractUserRepository,
        inventory_repo: AbstractInventoryRepository,
        item_template_repo: AbstractItemTemplateRepository,
        log_repo: AbstractLogRepository,
        config: Dict[str, Any]
    ):
        self.user_repo = user_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.log_repo = log_repo
        self.config = config

        # 自动钓鱼线程相关属性
        self.auto_fishing_thread: Optional[threading.Thread] = None
        self.auto_fishing_running = False

    def toggle_auto_fishing(self, user_id: str) -> Dict[str, Any]:
        """
        切换用户的自动钓鱼状态。

        Args:
            user_id: 用户ID。

        Returns:
            一个包含操作结果的字典。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "❌您还没有注册，请先使用 /注册 命令注册。"}

        user.auto_fishing_enabled = not user.auto_fishing_enabled
        self.user_repo.update(user)

        if user.auto_fishing_enabled:
            return {"success": True, "message": "🎣 自动钓鱼已开启！"}
        else:
            return {"success": True, "message": "🚫 自动钓鱼已关闭！"}

    def go_fish(self, user_id: str) -> Dict[str, Any]:
        """
        执行一次完整的钓鱼动作。

        Args:
            user_id: 尝试钓鱼的用户ID。

        Returns:
            一个包含结果的字典。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在，无法钓鱼。"}

        # 1. 检查成本
        fishing_cost = self.config.get('fishing', {}).get('cost', 10)
        if not user.can_afford(fishing_cost):
            return {"success": False, "message": f"金币不足，需要 {fishing_cost} 金币。"}

        # 先扣除成本
        user.coins -= fishing_cost

        # 2. 计算各种加成和修正值
        base_success_rate = 0.7
        quality_modifier = 1.0
        rare_chance = 0.0

        # 获取装备并应用加成
        equipped_rod_instance = self.inventory_repo.get_user_equipped_rod(user.user_id)
        if equipped_rod_instance:
            rod_template = self.item_template_repo.get_rod_by_id(equipped_rod_instance.rod_id)
            if rod_template:
                quality_modifier *= rod_template.bonus_fish_quality_modifier
                rare_chance += rod_template.bonus_rare_fish_chance

        equipped_accessory_instance = self.inventory_repo.get_user_equipped_accessory(user.user_id)
        if equipped_accessory_instance:
            acc_template = self.item_template_repo.get_accessory_by_id(equipped_accessory_instance.accessory_id)
            if acc_template:
                quality_modifier *= acc_template.bonus_fish_quality_modifier
                rare_chance += acc_template.bonus_rare_fish_chance
                # 海洋之心特殊效果：减少CD（在main.py中检查，此处不处理）

        # TODO: 此处应添加更复杂的鱼饵效果逻辑

        # 3. 判断是否成功钓到
        if random.random() >= base_success_rate:
            # 失败逻辑
            user.last_fishing_time = get_now()
            self.user_repo.update(user)
            return {"success": False, "message": "💨 什么都没钓到..."}

        # 4. 成功，生成渔获
        # TODO: 此处应添加原service.py中复杂的稀有度计算、鱼种选择逻辑
        # 为简化示例，我们随机选择一条鱼
        fish_template = self.item_template_repo.get_random_fish()
        if not fish_template:
             return {"success": False, "message": "错误：鱼类模板库为空！"}

        # 计算最终属性
        weight = random.randint(fish_template.min_weight, fish_template.max_weight)
        value = int(fish_template.base_value * quality_modifier)

        # 5. 更新数据库
        self.inventory_repo.add_fish_to_inventory(user.user_id, fish_template.fish_id)

        # 更新用户统计数据
        user.total_fishing_count += 1
        user.total_weight_caught += weight
        user.total_coins_earned += value # 注意：这里的逻辑与原代码不同，原代码是在卖出时才增加 total_coins_earned
        user.last_fishing_time = get_now()
        self.user_repo.update(user)

        # 记录日志
        record = FishingRecord(
            record_id=0, # DB自增
            user_id=user.user_id,
            fish_id=fish_template.fish_id,
            weight=weight,
            value=value,
            timestamp=user.last_fishing_time,
            rod_instance_id=user.equipped_rod_instance_id,
            accessory_instance_id=user.equipped_accessory_instance_id
        )
        self.log_repo.add_fishing_record(record)

        # 6. 构建成功返回结果
        return {
            "success": True,
            "fish": {
                "name": fish_template.name,
                "rarity": fish_template.rarity,
                "weight": weight,
                "value": value
            }
        }

    def get_user_pokedex(self, user_id: str) -> Dict[str, Any]:
        """获取用户的图鉴信息。"""
        # TODO: 实现获取用户图鉴的逻辑
        pass

    def start_auto_fishing_task(self):
        """启动自动钓鱼的后台线程。"""
        if self.auto_fishing_thread and self.auto_fishing_thread.is_alive():
            logger.info("自动钓鱼线程已在运行中")
            return

        self.auto_fishing_running = True
        self.auto_fishing_thread = threading.Thread(target=self._auto_fishing_loop, daemon=True)
        self.auto_fishing_thread.start()
        logger.info("自动钓鱼线程已启动")

    def stop_auto_fishing_task(self):
        """停止自动钓鱼的后台线程。"""
        self.auto_fishing_running = False
        if self.auto_fishing_thread:
            self.auto_fishing_thread.join(timeout=1.0)
            logger.info("自动钓鱼线程已停止")

    def _auto_fishing_loop(self):
        """自动钓鱼循环任务，由后台线程执行。"""
        fishing_config = self.config.get('fishing', {})
        cooldown = fishing_config.get('cooldown_seconds', 180)
        cost = fishing_config.get('cost', 10)

        while self.auto_fishing_running:
            try:
                # 获取所有开启自动钓鱼的用户
                auto_users_ids = self.user_repo.get_all_user_ids(auto_fishing_only=True)

                for user_id in auto_users_ids:
                    user = self.user_repo.get_by_id(user_id)
                    if not user:
                        continue

                    # 检查CD
                    now_ts = get_now().timestamp()
                    last_ts = user.last_fishing_time.timestamp() if user.last_fishing_time else 0
                    if now_ts - last_ts < cooldown:
                        continue # CD中，跳过

                    # 检查成本
                    if not user.can_afford(cost):
                        # 金币不足，关闭其自动钓鱼
                        user.auto_fishing_enabled = False
                        self.user_repo.update(user)
                        logger.warning(f"用户 {user_id} 金币不足，已关闭自动钓鱼")
                        continue

                    # 执行钓鱼
                    result = self.go_fish(user_id)
                    if result['success']:
                        fish = result["fish"]
                        logger.info(f"用户 {user_id} 自动钓鱼成功: {fish['name']}")
                    else:
                         logger.info(f"用户 {user_id} 自动钓鱼失败: {result['message']}")

                # 每轮检查间隔
                time.sleep(40)

            except Exception as e:
                logger.error(f"自动钓鱼任务出错: {e}")
                time.sleep(60)