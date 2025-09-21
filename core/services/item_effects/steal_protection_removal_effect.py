from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item

class StealProtectionRemovalEffect(AbstractItemEffect):
    effect_type = "STEAL_PROTECTION_REMOVAL"

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        """
        驱灵香效果：用于驱散目标玩家的海灵守护效果。
        命令使用：/驱灵 @目标用户
        """
        # 驱灵香不支持通过通用“使用道具”入口直接生效
        # 引导用户使用专用指令
        message = "请使用指令：/驱灵 @目标用户 来驱散其海灵守护。"

        return {"success": False, "message": message}
