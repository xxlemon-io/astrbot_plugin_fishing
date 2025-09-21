from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from ...repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractUserBuffRepository,
)
from ...domain.models import User, Item


class AbstractItemEffect(ABC):
    """
    道具效果的抽象基类。
    所有具体的效果都应继承此类并实现 apply 方法。
    """

    effect_type: str = "ABSTRACT_EFFECT"

    def __init__(
        self,
        user_repo: Optional[AbstractUserRepository] = None,
        buff_repo: Optional[AbstractUserBuffRepository] = None,
        **kwargs,
    ):
        """
        构造函数，用于依赖注入。
        """
        self.user_repo = user_repo
        self.buff_repo = buff_repo

    @abstractmethod
    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any], quantity: int = 1
    ) -> Dict[str, Any]:
        """
        应用道具效果。

        Args:
            user: 目标用户对象。
            item_template: 被使用的道具模板对象。
            payload: 从 item_template.effect_payload 解析出的字典。
            quantity: 使用的道具数量。

        Returns:
            一个包含结果信息的字典，至少应有 "success": bool 和 "message": str。
        """
        pass
