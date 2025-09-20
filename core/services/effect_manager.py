import pkgutil
import importlib
from typing import Dict, Optional

from .item_effects.abstract_effect import AbstractItemEffect
from ..repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractUserBuffRepository,
)
from astrbot.api import logger


class EffectManager:
    def __init__(self):
        self._effects: Dict[str, AbstractItemEffect] = {}

    def discover_and_register(
        self,
        effects_package_path: str,
        dependencies: Dict[str, any]
    ):
        """
        自动发现并注册指定包路径下的所有效果处理器。
        """
        logger.info(f"正在从 '{effects_package_path}' 自动发现道具效果...")

        package = importlib.import_module(effects_package_path)

        for _, name, _ in pkgutil.iter_modules(package.__path__):
            try:
                module = importlib.import_module(f"{effects_package_path}.{name}")
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if (
                        isinstance(attribute, type) and
                        issubclass(attribute, AbstractItemEffect) and
                        attribute is not AbstractItemEffect
                    ):
                        # 实例化效果类，并动态注入所有可用的依赖
                        effect_instance = attribute(**dependencies)

                        effect_type = getattr(effect_instance, "effect_type", None)
                        if effect_type:
                            self.register(effect_type, effect_instance)
                            logger.info(f"  -> 已注册效果: '{effect_type}'")
                        else:
                            logger.warning(f"效果类 {attribute.__name__} 未定义 effect_type 属性，已跳过。")
            except Exception as e:
                logger.error(f"导入或注册效果模块 '{name}' 时失败: {e}", exc_info=True)

    def register(self, effect_type: str, effect_handler: AbstractItemEffect):
        """
        注册一个效果处理器。
        """
        if effect_type in self._effects:
            raise ValueError(f"效果类型 '{effect_type}' 已被注册。")
        self._effects[effect_type] = effect_handler

    def get_effect(self, effect_type: str) -> Optional[AbstractItemEffect]:
        """
        根据效果类型获取对应的处理器实例。
        """
        return self._effects.get(effect_type)
