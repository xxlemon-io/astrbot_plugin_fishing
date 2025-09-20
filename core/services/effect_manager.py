from typing import Dict, Optional

from .item_effects.abstract_effect import AbstractItemEffect


class EffectManager:
    def __init__(self):
        self._effects: Dict[str, AbstractItemEffect] = {}

    def register(self, effect_type: str, effect_handler: AbstractItemEffect):
        """
        注册一个效果处理器。
        """
        if effect_type in self._effects:
            # 在实际应用中，你可能希望这里能抛出一个更具体的异常
            raise ValueError(f"Effect type '{effect_type}' is already registered.")
        self._effects[effect_type] = effect_handler

    def get_effect(self, effect_type: str) -> Optional[AbstractItemEffect]:
        """
        根据效果类型获取对应的处理器实例。
        """
        return self._effects.get(effect_type)
