from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item

class StealProtectionRemovalEffect(AbstractItemEffect):
    effect_type = "STEAL_PROTECTION_REMOVAL"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        """
        驱灵香效果：移除目标玩家的海灵守护效果
        注意：这个效果需要在偷窃时指定目标使用
        """
        # 这个效果需要在偷窃逻辑中特殊处理
        # 这里只是标记用户使用了驱灵香
        message = f"🔥 驱灵香已准备就绪！下次偷窃时将直接驱散目标的海灵守护！"
        
        return {"success": True, "message": message}
