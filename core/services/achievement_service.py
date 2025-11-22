import threading
import time
import pkgutil
import inspect
import sqlite3
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
            max_wipe_bomb_multiplier=user.max_wipe_bomb_multiplier, # <--- 采用优化后的实现
            min_wipe_bomb_multiplier=user.min_wipe_bomb_multiplier, # <--- 采用优化后的实现
            owned_rod_rarities=owned_rod_rarities,
            owned_accessory_rarities=owned_accessory_rarities,
            has_heavy_fish=self.achievement_repo.has_caught_heavy_fish(user_id, 100000)
        )

    def _grant_reward(self, user: User, achievement: BaseAchievement) -> bool:
        """
        根据成就定义，为用户发放奖励。
        (修正版，适配从 achievement.reward 元组中解析奖励信息)
        返回 True 表示奖励发放成功，False 表示失败（此时需要管理员手动发放）
        """
        # 1. 防御性检查：确保 reward 属性存在且不为 None
        if not hasattr(achievement, 'reward') or achievement.reward is None:
            logger.info(f"成就 '{achievement.name}' (ID: {achievement.id}) 没有定义奖励，仅解锁成就本身。")
            # 没有奖励时，视为成功（可以解锁成就）
            return True

        # 2. 安全地解析 reward 元组
        try:
            reward_tuple = achievement.reward
            if len(reward_tuple) == 3:
                reward_type, reward_value, reward_quantity = reward_tuple
            elif len(reward_tuple) == 2:
                reward_type, reward_value = reward_tuple
                reward_quantity = 1  # 如果元组只有2个元素，数量默认为1
            else:
                logger.error(f"成就 '{achievement.name}' 的 reward 属性格式不正确（需要2或3个元素）: {reward_tuple}")
                return False
                
        except (TypeError, ValueError) as e:
            logger.error(f"解析成就 '{achievement.name}' 的 reward 属性时失败: {achievement.reward}。错误: {e}")
            return False

        # 打印日志，方便调试
        logger.info(f"正在为用户 {user.user_id} 发放成就 '{achievement.name}' 的奖励: "
                    f"类型='{reward_type}', 值='{reward_value}', 数量={reward_quantity}")

        # 3. 根据解析出的 reward_type 分发奖励
        try:
            if reward_type == "coins":
                return self._grant_coins_reward(user, achievement, reward_value, reward_quantity)
            elif reward_type == "title":
                return self._grant_title_reward(user, achievement, reward_value)
            elif reward_type == "bait":
                return self._grant_bait_reward(user, achievement, reward_value, reward_quantity)
            elif reward_type == "rod":
                return self._grant_rod_reward(user, achievement, reward_value, reward_quantity)
            elif reward_type == "accessory":
                return self._grant_accessory_reward(user, achievement, reward_value, reward_quantity)
            else:
                logger.warning(f"未知的成就奖励类型: '{reward_type}'，无法发放。")
                return False
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
            # 只捕获预期的数据库完整性错误，避免掩盖编程错误
            logger.error(f"发放成就奖励时发生数据库错误: {e}", exc_info=True)
            return False
        # 其他异常（如 AttributeError, KeyError 等）应该重新抛出，以便发现编程错误

    def _grant_coins_reward(self, user: User, achievement: BaseAchievement, reward_value: int, reward_quantity: int) -> bool:
        """发放金币奖励"""
        if not isinstance(reward_value, int) or not isinstance(reward_quantity, int):
            logger.error(f"成就 '{achievement.name}' 的金币奖励值或数量不是整数。")
            return False
        
        amount_to_add = reward_value * reward_quantity
        user.coins += amount_to_add
        self.user_repo.update(user)
        logger.info(f"已为用户 {user.user_id} 添加 {amount_to_add} 金币。")
        return True

    def _grant_title_reward(self, user: User, achievement: BaseAchievement, reward_value: int) -> bool:
        """发放称号奖励"""
        self.achievement_repo.grant_title_to_user(user.user_id, reward_value)
        return True

    def _grant_bait_reward(self, user: User, achievement: BaseAchievement, reward_value: int, reward_quantity: int) -> bool:
        """发放鱼饵奖励"""
        bait_template = self.item_template_repo.get_bait_by_id(reward_value)
        if not bait_template:
            logger.error(f"尝试奖励鱼饵失败：找不到ID为 {reward_value} 的鱼饵模板。成就: '{achievement.name}' (ID: {achievement.id})")
            return False
        
        self.inventory_repo.update_bait_quantity(user.user_id, reward_value, delta=reward_quantity)
        logger.info(f"已为用户 {user.user_id} 添加 {reward_quantity} 个 {bait_template.name} (ID: {reward_value})。")
        return True

    def _grant_rod_reward(self, user: User, achievement: BaseAchievement, reward_value: int, reward_quantity: int) -> bool:
        """发放鱼竿奖励"""
        rod_template = self.item_template_repo.get_rod_by_id(reward_value)
        if not rod_template:
            logger.error(f"尝试奖励鱼竿失败：找不到ID为 {reward_value} 的鱼竿模板。成就: '{achievement.name}' (ID: {achievement.id})")
            return False
        
        for _ in range(reward_quantity):
            self.inventory_repo.add_rod_instance(user.user_id, reward_value, rod_template.durability)
        logger.info(f"已为用户 {user.user_id} 添加 {reward_quantity} 个 {rod_template.name} (ID: {reward_value})。")
        return True

    def _grant_accessory_reward(self, user: User, achievement: BaseAchievement, reward_value: int, reward_quantity: int) -> bool:
        """发放饰品奖励"""
        accessory_template = self.item_template_repo.get_accessory_by_id(reward_value)
        if not accessory_template:
            logger.error(f"尝试奖励饰品失败：找不到ID为 {reward_value} 的饰品模板。成就: '{achievement.name}' (ID: {achievement.id})")
            return False
        
        for _ in range(reward_quantity):
            self.inventory_repo.add_accessory_instance(user.user_id, reward_value)
        logger.info(f"已为用户 {user.user_id} 添加 {reward_quantity} 个 {accessory_template.name} (ID: {reward_value})。")
        return True
            
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
                # 无论奖励是否成功，成就都会解锁；如果奖励失败，记录错误信息供管理员处理
                reward_success = self._grant_reward(user_context.user, ach)
                if not reward_success:
                    logger.error(
                        f"【成就奖励发放失败，需要管理员手动处理】"
                        f"用户ID: {user_id}, "
                        f"成就名称: '{ach.name}' (ID: {ach.id}), "
                        f"奖励信息: {ach.reward if hasattr(ach, 'reward') and ach.reward else '无奖励'}"
                    )
                # 无论奖励是否成功，成就都会解锁
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