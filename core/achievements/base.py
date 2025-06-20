from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, Any, Set

from ..domain.models import User

@dataclass
class UserContext:
    """
    一个数据容器，封装了检查成就时可能需要的所有用户相关数据。
    由 AchievementService 在检查前填充。
    """
    user: User
    unique_fish_count: int
    garbage_count: int
    max_wipe_bomb_multiplier: float
    owned_rod_rarities: Set[int]
    owned_accessory_rarities: Set[int]
    has_heavy_fish: bool



class BaseAchievement(ABC):
    """所有成就类的抽象基类（接口）"""

    # 每个子类都必须定义这些属性
    id: int
    name: str
    target_value: Any
    description: str
    # 奖励定义: (类型, 值, 数量) e.g., ('coins', 500, 1) or ('title', 3, 1)
    reward: Tuple[str, int, int]

    @abstractmethod
    def get_progress(self, context: UserContext) -> int:
        """获取并返回此成就的当前进度值。"""
        pass

    @abstractmethod
    def check(self, context: UserContext) -> bool:
        """
        核心检查逻辑。
        如果用户满足此成就的条件，则返回 True。
        """
        pass
