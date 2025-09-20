from datetime import datetime
from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ....core.domain.models import User, Item


class ResetFishingCooldownEffect(AbstractItemEffect):
    effect_type = "RESET_FISHING_COOLDOWN"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        # 将用户的上次钓鱼时间设置为一个很早的时间点，相当于重置了CD
        user.last_fishing_time = datetime.min
        self.user_repo.update(user)

        return {"success": True, "message": "⚙️ 钓鱼冷却已重置！"}
