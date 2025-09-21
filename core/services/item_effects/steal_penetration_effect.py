from datetime import datetime, timedelta
from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item, UserBuff
from ...utils import get_now

class StealPenetrationEffect(AbstractItemEffect):
    effect_type = "STEAL_PENETRATION_BUFF"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        """
        破灵符效果：获得穿透海灵守护的能力
        """
        duration_hours = payload.get("duration_hours", 1)  # 默认1小时
        total_duration_hours = duration_hours * quantity
        
        existing_buff = self.buff_repo.get_active_by_user_and_type(
            user.user_id, self.effect_type
        )
        
        now = get_now().replace(tzinfo=None)

        if existing_buff:
            # 如果 buff 已过期，则从当前时间开始计算；否则，在原过期时间上叠加
            start_time = max(now, existing_buff.expires_at)
            new_expires_at = start_time + timedelta(hours=total_duration_hours)
            existing_buff.expires_at = new_expires_at
            self.buff_repo.update(existing_buff)
            
            total_remaining_seconds = (new_expires_at - now).total_seconds()
            total_remaining_hours = total_remaining_seconds / 3600
            message = f"⚡ 破灵符的力量已叠加，你将在接下来 {total_remaining_hours:.1f} 小时内可以穿透海灵守护！"
        else:
            # 创建新buff
            new_expires_at = now + timedelta(hours=total_duration_hours)
            new_buff = UserBuff(
                id=0,
                user_id=user.user_id,
                buff_type=self.effect_type,
                payload=None,
                started_at=now,
                expires_at=new_expires_at,
            )
            self.buff_repo.add(new_buff)
            message = f"⚡ 破灵符激活！你将在未来 {total_duration_hours} 小时内获得穿透海灵守护的能力！"
            
        return {"success": True, "message": message}
