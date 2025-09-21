from datetime import datetime
from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item


class ResetStealCooldownEffect(AbstractItemEffect):
    effect_type = "RESET_STEAL_COOLDOWN"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        if quantity > 1:
            return {
                "success": False,
                "message": f"【{item_template.name}】不支持批量使用，请一次使用一个。"
            }
        user.last_steal_time = datetime.min
        self.user_repo.update(user)

        return {"success": True, "message": "🕒 偷鱼冷却已重置！"}
