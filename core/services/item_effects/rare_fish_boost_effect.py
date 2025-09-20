import json
from datetime import datetime, timedelta
from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ....core.domain.models import User, Item, UserBuff


class RareFishBoostEffect(AbstractItemEffect):
    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        duration_seconds = payload.get("duration_seconds", 600)
        multiplier = payload.get("multiplier", 1.5)

        existing_buff = self.buff_repo.get_active_by_user_and_type(
            user.user_id, "RARE_FISH_BOOST"
        )

        if existing_buff:
            existing_buff.expires_at = datetime.now() + timedelta(
                seconds=duration_seconds
            )
            self.buff_repo.delete(existing_buff.id)
            self.buff_repo.add(existing_buff)
            return {
                "success": True,
                "message": f"✨ 幸运效果已刷新，持续时间重置为 {duration_seconds // 60} 分钟！",
            }
        else:
            new_buff = UserBuff(
                id=None,
                user_id=user.user_id,
                buff_type="RARE_FISH_BOOST",
                payload=json.dumps({"multiplier": multiplier}),
                started_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=duration_seconds),
            )
            self.buff_repo.add(new_buff)
            return {
                "success": True,
                "message": f"✨ 接下来的 {duration_seconds // 60} 分钟内，钓到稀有鱼的概率提升了！",
            }
