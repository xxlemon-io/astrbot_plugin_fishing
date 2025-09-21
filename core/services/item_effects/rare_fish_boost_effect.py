import json
from datetime import datetime, timedelta
from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item, UserBuff
from ...utils import get_now


class RareFishBoostEffect(AbstractItemEffect):
    effect_type = "RARE_FISH_BOOST"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        duration_seconds = payload.get("duration_seconds", 600)
        multiplier = payload.get("multiplier", 1.5)
        
        total_duration_seconds = duration_seconds * quantity

        existing_buff = self.buff_repo.get_active_by_user_and_type(
            user.user_id, "RARE_FISH_BOOST"
        )

        now = get_now().replace(tzinfo=None)
        if existing_buff:
            # 如果 buff 已过期，则从当前时间开始计算；否则，在原过期时间上叠加
            start_time = max(now, existing_buff.expires_at)
            new_expires_at = start_time + timedelta(seconds=total_duration_seconds)
            
            existing_buff.expires_at = new_expires_at
            # 更新 payload（如果需要）
            existing_buff.payload = json.dumps({"multiplier": multiplier})
            self.buff_repo.update(existing_buff)
            
            total_remaining_seconds = (new_expires_at - now).total_seconds()
            total_remaining_minutes = int(total_remaining_seconds / 60)
            
            return {
                "success": True,
                "message": f"✨ 幸运效果已叠加！总持续时间延长至 {total_remaining_minutes} 分钟。",
            }
        else:
            new_expires_at = now + timedelta(seconds=total_duration_seconds)
            new_buff = UserBuff(
                id=None,
                user_id=user.user_id,
                buff_type="RARE_FISH_BOOST",
                payload=json.dumps({"multiplier": multiplier}),
                started_at=now,
                expires_at=new_expires_at,
            )
            self.buff_repo.add(new_buff)
            
            total_minutes = total_duration_seconds // 60
            return {
                "success": True,
                "message": f"✨ 接下来的 {total_minutes} 分钟内，钓到稀有鱼的概率提升了！",
            }
