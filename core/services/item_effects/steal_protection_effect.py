from datetime import datetime, timedelta
from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ....core.domain.models import User, Item, UserBuff
from ....core.utils import get_now

class StealProtectionEffect(AbstractItemEffect):
    effect_type = "STEAL_PROTECTION_BUFF"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        duration_hours = payload.get("duration_hours", 8)
        
        existing_buff = self.buff_repo.get_active_by_user_and_type(
            user.user_id, self.effect_type
        )
        
        expires_at = get_now() + timedelta(hours=duration_hours)

        if existing_buff:
            # 刷新现有buff的过期时间
            existing_buff.expires_at = expires_at
            self.buff_repo.update(existing_buff)
            message = f"🛡️ 守护海灵的庇护时间已刷新，你的鱼塘将在接下来 {duration_hours} 小时内免受偷窃！"
        else:
            # 创建新buff
            new_buff = UserBuff(
                id=0,
                user_id=user.user_id,
                buff_type=self.effect_type,
                payload=None,
                started_at=get_now(),
                expires_at=expires_at,
            )
            self.buff_repo.add(new_buff)
            message = f"🌊 一个温和的海灵出现了，它将在未来 {duration_hours} 小时内守护你的鱼塘！"
            
        return {"success": True, "message": message}
