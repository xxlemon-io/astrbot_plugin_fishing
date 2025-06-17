import random
from typing import Dict, Any
from datetime import datetime, date, timedelta, timezone

# 导入仓储接口和领域模型
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractLogRepository,
    AbstractInventoryRepository,
    AbstractItemTemplateRepository
)
from ..domain.models import User, TaxRecord
from ..utils import get_now, get_today


class UserService:
    """封装与用户相关的业务逻辑"""

    def __init__(
        self,
        user_repo: AbstractUserRepository,
        log_repo: AbstractLogRepository,
        inventory_repo: AbstractInventoryRepository,
        item_template_repo: AbstractItemTemplateRepository,
        config: Dict[str, Any]  # 注入游戏配置
    ):
        self.user_repo = user_repo
        self.log_repo = log_repo
        self.inventory_repo = inventory_repo
        self.item_template_repo = item_template_repo
        self.config = config

    def register(self, user_id: str, nickname: str) -> Dict[str, Any]:
        """
        注册新用户。

        Args:
            user_id: 用户ID
            nickname: 用户昵称

        Returns:
            一个包含成功状态和消息的字典。
        """
        if self.user_repo.check_exists(user_id):
            return {"success": False, "message": "用户已注册"}

        initial_coins = self.config.get('user', {}).get('initial_coins', 200)
        new_user = User(
            user_id=user_id,
            nickname=nickname,
            coins=initial_coins,
            created_at=get_now()
        )
        self.user_repo.add(new_user)
        return {
            "success": True,
            "message": f"注册成功！欢迎 {nickname} 🎉 你获得了 {initial_coins} 金币作为起始资金。"
        }

    def get_leaderboard_data(self, limit: int = 10) -> Dict[str, Any]:
        """
        获取排行榜数据。

        Args:
            limit: 返回的用户数量限制

        Returns:
            包含排行榜数据的字典。
        """
        leaderboard_data = self.user_repo.get_leaderboard_data(limit)
        return {
            "success": True,
            "leaderboard": leaderboard_data
        }

    def daily_sign_in(self, user_id: str) -> Dict[str, Any]:
        """
        处理用户每日签到。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "请先注册才能签到"}

        today = get_today()
        if self.log_repo.has_checked_in(user_id, today):
            return {"success": False, "message": "你今天已经签到过了，明天再来吧！"}

        # 检查是否需要重置连续登录天数
        yesterday = today - timedelta(days=1)
        if not self.log_repo.has_checked_in(user_id, yesterday):
            user.consecutive_login_days = 0 # 不是连续签到，重置

        # 计算签到奖励
        signin_config = self.config.get('signin', {})
        min_reward = signin_config.get('min_reward', 100)
        max_reward = signin_config.get('max_reward', 300)
        coins_reward = random.randint(min_reward, max_reward)

        user.coins += coins_reward
        user.consecutive_login_days += 1
        user.last_login_time = get_now()

        # 检查连续签到奖励
        bonus_coins = 0
        consecutive_bonuses = signin_config.get('consecutive_bonuses', {})
        if str(user.consecutive_login_days) in consecutive_bonuses:
            bonus_coins = consecutive_bonuses[str(user.consecutive_login_days)]
            user.coins += bonus_coins

        # 更新数据库
        self.user_repo.update(user)
        self.log_repo.add_check_in(user_id, today)

        message = f"签到成功！获得 {coins_reward} 金币。"
        if bonus_coins > 0:
            message += f" 连续签到 {user.consecutive_login_days} 天，额外奖励 {bonus_coins} 金币！"

        return {
            "success": True,
            "message": message,
            "coins_reward": coins_reward,
            "bonus_coins": bonus_coins,
            "consecutive_days": user.consecutive_login_days
        }

    def apply_daily_taxes(self) -> None:
        """对所有高价值用户征收每日税收。"""
        tax_config = self.config.get('tax', {})
        if tax_config.get("is_tax", False) is False:
            return
        threshold = tax_config.get('threshold', 1000000)
        step_coins = tax_config.get('step_coins', 1000000)
        step_rate = tax_config.get('step_rate', 0.01)
        min_rate = tax_config.get('min_rate', 0.001)
        max_rate = tax_config.get('max_rate', 0.35)

        high_value_users = self.user_repo.get_high_value_users(threshold)

        for user in high_value_users:
            tax_rate = 0.0
            # 根据资产确定税率
            if user.coins >= threshold:
                steps = (user.coins - threshold) // step_coins
                tax_rate = min_rate + steps * step_rate
                if tax_rate > max_rate:
                    tax_rate = max_rate
            if tax_rate > 0:
                tax_amount = int(user.coins * tax_rate)
                original_coins = user.coins
                user.coins -= tax_amount

                self.user_repo.update(user)

                tax_log = TaxRecord(
                    tax_id=0, # DB会自增
                    user_id=user.user_id,
                    tax_amount=tax_amount,
                    tax_rate=tax_rate,
                    original_amount=original_coins,
                    balance_after=user.coins,
                    timestamp=get_now(),
                    tax_type='每日资产税'
                )
                self.log_repo.add_tax_record(tax_log)

    def get_user_titles(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户拥有的称号列表。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        owned_titles = self.inventory_repo.get_user_titles(user_id)
        if not owned_titles:
            return {"success": True, "titles": []}

        titles_data = []
        for title in owned_titles:
            title_template = self.item_template_repo.get_title_by_id(title)
            if title_template:
                titles_data.append({
                    "title_id": title,
                    "name": title_template.name,
                    "description": title_template.description,
                    "is_current": (title == user.current_title_id)
                })

        return {
            "success": True,
            "titles": titles_data
        }

    def use_title(self, user_id: str, title_id: int) -> Dict[str, Any]:
        """
        装备一个称号。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}

        owned_titles = self.inventory_repo.get_user_titles(user_id)
        if title_id not in [t for t in owned_titles]:
            return {"success": False, "message": "你没有这个称号，无法使用"}

        user.current_title_id = title_id
        self.user_repo.update(user)

        # 可以从ItemTemplateRepo获取称号名字来丰富返回信息
        title_template = self.item_template_repo.get_title_by_id(title_id)
        return {"success": True, "message": f"✅ 成功装备 {title_template.name}！"}

    def get_user_currency(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的货币信息。
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在", "coins": 0, "premium_currency": 0}

        return {
            "success": True,
            "coins": user.coins,
            "premium_currency": user.premium_currency
        }