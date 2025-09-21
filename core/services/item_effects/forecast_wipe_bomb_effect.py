from typing import Dict, Any

from .abstract_effect import AbstractItemEffect
from ...domain.models import User, Item
from ..game_mechanics_service import GameMechanicsService


class ForecastWipeBombEffect(AbstractItemEffect):
    """
    使用时运沙漏来预知下一次擦弹结果的效果。
    """
    effect_type = "FORECAST_WIPE_BOMB"

    def __init__(self, user_repo=None, buff_repo=None, **kwargs):
        super().__init__(user_repo, buff_repo, **kwargs)
        # 效果处理器需要依赖 GameMechanicsService 来执行预测逻辑
        game_mechanics_service = kwargs.get("game_mechanics_service")
        if not game_mechanics_service:
            raise ValueError("GameMechanicsService 实例是必需的。")
        self.game_mechanics_service = game_mechanics_service

    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        if quantity > 1:
            return {
                "success": False,
                "message": f"【{item_template.name}】不支持批量使用，请一次使用一个。"
            }
        # 直接调用现有的预测服务
        result = self.game_mechanics_service.forecast_wipe_bomb(user.user_id)
        
        # forecast_wipe_bomb 已经返回了包含 success 和 message 的字典，直接透传即可
        return result
