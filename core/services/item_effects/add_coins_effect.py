from typing import Dict, Any
import json
import random

from .abstract_effect import AbstractItemEffect
from ....core.domain.models import User, Item


class AddCoinsEffect(AbstractItemEffect):
    effect_type = "ADD_COINS"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        min_amount = payload.get("min_amount")
        max_amount = payload.get("max_amount")

        if min_amount is not None and max_amount is not None:
            # 随机金额
            if min_amount >= max_amount:
                return {"success": False, "message": "无效的随机金额范围"}
            amount = random.randint(min_amount, max_amount)
        else:
            # 固定金额
            amount = payload.get("amount", 0)

        if not isinstance(amount, int) or amount <= 0:
            return {"success": False, "message": "无效的金币道具"}

        user.coins += amount
        self.user_repo.update(user)

        return {"success": True, "message": f"💰 打开 {item_template.name}，获得了 {amount} 金币！"}
