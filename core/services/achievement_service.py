import threading
import time
import pkgutil
import inspect
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from astrbot.api import logger

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractAchievementRepository,
    AbstractUserRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository,
    AbstractLogRepository
)
from ..domain.models import User
from ..achievements.base import BaseAchievement, UserContext

class AchievementService:
    """实现可插拔的成就系统"""

    def __init__(
        self,
        achievement_repo: AbstractAchievementRepository,
        user_repo: AbstractUserRepository,
        inventory_repo: AbstractInventoryRepository,
        item_template_repo: AbstractItemTemplateRepository,
        log_repo: AbstractLogRepository
    ):
        self.achievement_repo = achievement_repo
        self.user_repo = user_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.log_repo = log_repo

        self.achievements: List[BaseAchievement] = self._load_achievements()

        self.achievement_check_thread: Optional[threading.Thread] = None
        self.achievement_check_running = False

    def _load_achievements(self) -> List[BaseAchievement]:
        """动态扫描并加载所有成就类。"""
        loaded_achievements = []
        # 成就模块都在 core.achievements 包下
        from .. import achievements as achievements_package

        for _, name, _ in pkgutil.walk_packages(achievements_package.__path__, achievements_package.__name__ + "."):
            module = __import__(name, fromlist="dummy")
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseAchievement) and obj is not BaseAchievement:
                    loaded_achievements.append(obj())
        logger.info(f"成功加载 {len(loaded_achievements)} 个成就模块。")
        return loaded_achievements

    def _build_user_context(self, user_id: str) -> Optional[UserContext]:
        """为用户构建一个包含所有检查所需数据的上下文对象。"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return None

        owned_rod_rarities: Set[int] = set()
        for rod_instance in self.inventory_repo.get_user_rod_instances(user_id):
            rod_template = self.item_template_repo.get_rod_by_id(rod_instance.rod_id)
            if rod_template:
                owned_rod_rarities.add(rod_template.rarity)

        owned_accessory_rarities: Set[int] = set()
        for acc_instance in self.inventory_repo.get_user_accessory_instances(user_id):
            acc_template = self.item_template_repo.get_accessory_by_id(acc_instance.accessory_id)
            if acc_template:
                owned_accessory_rarities.add(acc_template.rarity)

        return UserContext(
            user=user,
            unique_fish_count=self.achievement_repo.get_user_unique_fish_count(user_id),
            garbage_count=self.achievement_repo.get_user_garbage_count(user_id),
            max_wipe_bomb_multiplier=self.log_repo.get_max_wipe_bomb_multiplier(user_id),
            owned_rod_rarities=owned_rod_rarities,
            owned_accessory_rarities=owned_accessory_rarities,
            has_heavy_fish=self.achievement_repo.has_caught_heavy_fish(user_id, 100000)
        )

    def _grant_reward(self, user: User, achievement: BaseAchievement):
        """根据成就定义，为用户发放奖励。"""
        reward_type, reward_value, reward_quantity = achievement.reward
        if not reward_value:
            return

        if reward_type == "coins":
            user.coins += (reward_value * reward_quantity)
            self.user_repo.update(user)
        elif reward_type == "title":
            self.achievement_repo.grant_title_to_user(user.user_id, reward_value)
        elif reward_type == "bait":
            self.inventory_repo.update_bait_quantity(user.user_id, reward_value, delta=reward_quantity)
        elif reward_type == "rod":
            rod_template = self.item_template_repo.get_rod_by_id(reward_value)
            if rod_template:
                self.inventory_repo.add_rod_instance(user.user_id, reward_value, rod_template.durability)
        elif reward_type == "accessory":
            self.inventory_repo.add_accessory_instance(user.user_id, reward_value)

    # --- 后台任务与核心逻辑 ---

    def start_achievement_check_task(self):
        """启动成就检查的后台线程。"""
        if self.achievement_check_thread and self.achievement_check_thread.is_alive():
            return
        self.achievement_check_running = True
        self.achievement_check_thread = threading.Thread(target=self._achievement_check_loop, daemon=True)
        self.achievement_check_thread.start()

    def stop_achievement_check_task(self):
        """停止成就检查的后台线程。"""
        self.achievement_check_running = False
        if self.achievement_check_thread:
            self.achievement_check_thread.join(timeout=1.0)

    def _achievement_check_loop(self):
        """成就检查循环任务。"""
        while self.achievement_check_running:
            try:
                all_user_ids = self.user_repo.get_all_user_ids()
                for user_id in all_user_ids:
                    self._process_user_achievements(user_id)
                time.sleep(600) # 10分钟检查一次
            except Exception as e:
                logger.error(f"成就检查任务出错: {e}")
                logger.error("堆栈信息:", exc_info=True)
                time.sleep(60)

    def _process_user_achievements(self, user_id: str):
        """处理单个用户的成就检查和发放流程。"""
        user_context = self._build_user_context(user_id)
        if not user_context:
            return

        user_progress = self.achievement_repo.get_user_progress(user_id)

        for ach in self.achievements:
            # 如果成就已完成，则跳过
            if user_progress.get(ach.id, {}).get("completed_at"):
                continue
            # 调用每个成就自己的检查方法
            if ach.check(user_context):
                # 如果成就完成，发放奖励并更新进度
                self._grant_reward(user_context.user, ach)
                self.achievement_repo.update_user_progress(user_id, ach.id, ach.get_progress(user_context), completed_at=datetime.now())
    # --- 成就相关的API接口 ---

    def get_user_achievements(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的成就列表和进度。
        """
        user = self.user_repo.get_by_id(user_id)
        user_context = self._build_user_context(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        user_progress = self.achievement_repo.get_user_progress(user_id)
        achievements_data = []

        for ach in self.achievements:
            progress = user_progress.get(ach.id, {})
            if not progress:
                progress = {"progress": 0, "completed_at": None}
            achievements_data.append({
                "id": ach.id,
                "name": ach.name,
                "description": ach.description,
                "reward": ach.reward,
                "progress": ach.get_progress(user_context),
                "target": ach.target_value,
                "completed_at": progress.get("completed_at")
            })

        return {
            "success": True,
            "achievements": achievements_data
        }
