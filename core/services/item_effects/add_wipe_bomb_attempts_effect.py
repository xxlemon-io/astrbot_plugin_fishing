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

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        attempts_to_add = payload.get("amount", 1)
        buff_type = "WIPE_BOMB_ATTEMPTS_BOOST"

        # 查找现有buff
        existing_buff = self.buff_repo.get_active_by_user_and_type(
            user.user_id, buff_type
        )

        if existing_buff:
            # 如果buff已存在，累加次数
            current_payload = json.loads(existing_buff.payload or '{}')
            current_amount = current_payload.get("amount", 0)
            new_amount = current_amount + attempts_to_add
            
            existing_buff.payload = json.dumps({"amount": new_amount})
            existing_buff.expires_at = get_end_of_day()
            self.buff_repo.update(existing_buff)
            
            message = f"💣 擦弹次数已累加！今天总共额外增加了 {new_amount} 次。"

        else:
            # 如果buff不存在，创建新buff
            new_buff = UserBuff(
                id=0,
                user_id=user.user_id,
                buff_type=buff_type,
                payload=json.dumps({"amount": attempts_to_add}),
                started_at=get_now(),
                expires_at=get_end_of_day(),  # buff持续到当天结束
            )
            self.buff_repo.add(new_buff)
            message = f"💣 你获得了 {attempts_to_add} 次额外的擦弹机会，仅限今天有效！"

        return {"success": True, "message": message}
