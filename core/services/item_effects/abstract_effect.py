from abc import ABC, abstractmethod
from typing import Dict, Any

from ....core.repositories.abstract_repository import (
    AbstractUserRepository,
    AbstractUserBuffRepository,
)
from ....core.domain.models import User, Item


class AbstractItemEffect(ABC):
    def __init__(
        self,
        user_repo: AbstractUserRepository = None,
        buff_repo: AbstractUserBuffRepository = None,
    ):
        self.user_repo = user_repo
        self.buff_repo = buff_repo

    @abstractmethod
    def apply(
        self, user: User, item_template: Item, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        应用道具效果。

        Args:
            user: 目标用户对象。
            item_template: 被使用的道具模板对象。
            payload: 从 item_template.effect_payload 解析出的字典。

        Returns:
            一个包含结果信息的字典，至少应有 "success": bool 和 "message": str。
        """
        pass
