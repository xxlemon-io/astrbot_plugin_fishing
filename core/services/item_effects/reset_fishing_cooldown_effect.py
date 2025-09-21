from datetime import datetime, timedelta
from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item
from ...utils import get_now


class ResetFishingCooldownEffect(AbstractItemEffect):
    effect_type = "RESET_FISHING_COOLDOWN"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        if quantity > 1:
            return {
                "success": False,
                "message": f"【{item_template.name}】不支持批量使用，请一次使用一个。"
            }
            
        # 将用户的上次钓鱼时间设置为一个"很久以前"的时间点，确保跨时区/线程下也可立即钓鱼
        # 使用 datetime.min 但确保时区信息与 get_now() 一致
        now = get_now()
        user.last_fishing_time = datetime.min.replace(tzinfo=now.tzinfo)
        self.user_repo.update(user)

        return {"success": True, "message": "⚙️ 钓鱼冷却已重置！"}
