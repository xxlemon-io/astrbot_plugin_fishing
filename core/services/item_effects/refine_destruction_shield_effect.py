import json
from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item, UserBuff
from ...utils import get_now


class RefineDestructionShieldEffect(AbstractItemEffect):
    effect_type = "REFINE_DESTRUCTION_SHIELD"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        """为用户添加或叠加精炼护符次数。

        payload:
          - charges: 增加的可抵消毁坏次数，默认1
          - mode:    护符模式（预留），默认"keep"（保留本体不降级）
        """
        charges_per_item = int(payload.get("charges", 1))
        total_charges_to_add = charges_per_item * quantity
        mode = payload.get("mode", "keep")

        buff_type = "REFINE_DESTRUCTION_SHIELD"

        existing_buff = self.buff_repo.get_active_by_user_and_type(
            user.user_id, buff_type
        )

        if existing_buff:
            # 叠加次数
            try:
                current_payload = json.loads(existing_buff.payload or "{}")
            except Exception:
                current_payload = {}
            current_charges = int(current_payload.get("charges", 0))
            new_charges = max(0, current_charges + total_charges_to_add)

            existing_payload = {
                "charges": new_charges,
                "mode": current_payload.get("mode", mode),
            }
            existing_buff.payload = json.dumps(existing_payload)
            # 护符默认无限期；如需当日有效，可在此设置 expires_at
            self.buff_repo.update(existing_buff)

            return {
                "success": True,
                "message": f"🛡 精炼护符已叠加！当前可抵消毁坏次数：{new_charges}",
            }

        else:
            # 新建buff
            new_buff = UserBuff(
                id=0,
                user_id=user.user_id,
                buff_type=buff_type,
                payload=json.dumps({"charges": total_charges_to_add, "mode": mode}),
                started_at=get_now(),
                expires_at=None,
            )
            self.buff_repo.add(new_buff)
            return {
                "success": True,
                "message": f"🛡 获得精炼护符！可抵消毁坏次数：{total_charges_to_add}",
            }


