from datetime import datetime
from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item


class ResetStealCooldownEffect(AbstractItemEffect):
    effect_type = "RESET_STEAL_COOLDOWN"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        user.last_steal_time = datetime.min
        self.user_repo.update(user)

        return {"success": True, "message": "🕒 偷鱼冷却已重置！"}
