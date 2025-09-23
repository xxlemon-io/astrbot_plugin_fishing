from datetime import datetime, timedelta
from typing import Dict, Any
import json

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item, UserBuff
from ...utils import get_now


def get_end_of_day():
    now = get_now()
    return now.replace(hour=23, minute=59, second=59, microsecond=999999)


class AddWipeBombAttemptsEffect(AbstractItemEffect):
    effect_type = "WIPE_BOMB_ATTEMPTS_BOOST"

    def __init__(self, user_repo=None, buff_repo=None, **kwargs):
        super().__init__(user_repo, buff_repo, **kwargs)
        self.log_repo = kwargs.get("log_repo")
        self.game_config = kwargs.get("game_config")
        if not self.log_repo or not self.game_config:
            raise ValueError("LogRepository and GameConfig are required for this effect.")

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        attempts_per_item = payload.get("amount", 1)
        total_attempts_to_add = attempts_per_item * quantity
        
        buff_type = "WIPE_BOMB_ATTEMPTS_BOOST"
        new_amount = 0

        # 查找现有buff
        existing_buff = self.buff_repo.get_active_by_user_and_type(
            user.user_id, buff_type
        )

        if existing_buff:
            # 如果buff已存在，累加次数
            current_payload = json.loads(existing_buff.payload or '{}')
            current_amount = current_payload.get("amount", 0)
            new_amount = current_amount + total_attempts_to_add
            
            existing_buff.payload = json.dumps({"amount": new_amount})
            existing_buff.expires_at = get_end_of_day()
            self.buff_repo.update(existing_buff)

            # 重新获取最新的buff，确保读取到更新后的数据
            current_boost_buff = self.buff_repo.get_active_by_user_and_type(user.user_id, buff_type)
            if current_boost_buff and current_boost_buff.payload:
                try:
                    current_payload = json.loads(current_boost_buff.payload)
                    extra_attempts_after_update = current_payload.get("amount", 0)
                except json.JSONDecodeError:
                    extra_attempts_after_update = 0
            else:
                extra_attempts_after_update = 0

        else:
            # 如果buff不存在，创建新buff
            new_amount = total_attempts_to_add
            new_buff = UserBuff(
                id=0,
                user_id=user.user_id,
                buff_type=buff_type,
                payload=json.dumps({"amount": new_amount}),
                started_at=get_now(),
                expires_at=get_end_of_day(),  # buff持续到当天结束
            )
            self.buff_repo.add(new_buff)

            # 重新获取最新的buff，确保读取到更新后的数据
            current_boost_buff = self.buff_repo.get_active_by_user_and_type(user.user_id, buff_type)
            if current_boost_buff and current_boost_buff.payload:
                try:
                    current_payload = json.loads(current_boost_buff.payload)
                    extra_attempts_after_update = current_payload.get("amount", 0)
                except json.JSONDecodeError:
                    extra_attempts_after_update = 0
            else:
                extra_attempts_after_update = 0

        # 计算剩余次数
        base_max_attempts = self.game_config.get("wipe_bomb", {}).get("max_attempts_per_day", 3)
        total_max_attempts = base_max_attempts + extra_attempts_after_update
        used_attempts_today = self.log_repo.get_wipe_bomb_log_count_today(user.user_id)
        remaining_today = max(0, total_max_attempts - used_attempts_today)

        message = (
            f"🎫 你获得 {total_attempts_to_add} 次额外擦弹机会。"
            f"今天剩余擦弹次数：{remaining_today} 次 ({used_attempts_today}/{total_max_attempts})"
        )
        
        return {"success": True, "message": message}
