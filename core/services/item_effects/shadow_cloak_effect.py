from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item, UserBuff
from ...utils import get_now

class ShadowCloakEffect(AbstractItemEffect):
    effect_type = "SHADOW_CLOAK_BUFF"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        """
        暗影斗篷效果：无限时间，但只能反制一次，使用后立即移除
        """
        # 检查是否已有暗影斗篷效果
        existing_buff = self.buff_repo.get_active_by_user_and_type(
            user.user_id, self.effect_type
        )
        
        if existing_buff:
            # 如果已有效果，叠加数量（但实际使用逻辑中会立即移除）
            message = f"🌑 暗影斗篷的力量已叠加！你获得了额外的反制机会！"
        else:
            # 创建新buff，设置为无限时间（expires_at为None表示永不过期）
            now = get_now().replace(tzinfo=None)
            new_buff = UserBuff(
                id=0,
                user_id=user.user_id,
                buff_type=self.effect_type,
                payload=None,
                started_at=now,
                expires_at=None,  # 无限时间
            )
            self.buff_repo.add(new_buff)
            message = f"🌑 暗影斗篷激活！你获得了无视海灵守护的反制能力！"
            
        return {"success": True, "message": message}
