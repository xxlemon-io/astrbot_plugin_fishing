from typing import Dict, Any
import json

from .abstract_effect import AbstractItemEffect
from ....core.domain.models import User, Item


class AddCoinsEffect(AbstractItemEffect):
    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        amount = payload.get("amount", 0)
        if amount <= 0:
            return {"success": False, "message": "无效的金币道具"}

        user.coins += amount
        self.user_repo.update(user)

        return {"success": True, "message": f"💰 获得了 {amount} 金币！"}
