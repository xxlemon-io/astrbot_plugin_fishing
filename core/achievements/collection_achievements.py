from .base import BaseAchievement, UserContext

class UniqueFishSpecies10(BaseAchievement):
    id = 5
    name = "图鉴收集者I"
    description = "收集10种不同的鱼"
    reward = ('bait', 3, 5) # 奖励5个万能饵

    def get_progress(self, context: UserContext) -> int:
        """返回用户收集到的不同鱼种数量作为当前进度。"""
        return context.unique_fish_count

    def check(self, context: UserContext) -> bool:
        return context.unique_fish_count >= 10

class GarbageCollector50(BaseAchievement):
    id = 29
    name = "回收站常客"
    description = "累计钓上50个垃圾物品"
    reward = ('title', 9, 1) # 奖励 "回收大师" 称号

    def get_progress(self, context: UserContext) -> int:
        """返回用户钓到的垃圾总数作为当前进度。"""
        return context.garbage_count

    def check(self, context: UserContext) -> bool:
        return context.garbage_count >= 50

class RareRodCollected(BaseAchievement):
    id = 15
    name = "鸟枪换炮"
    description = "获得一个稀有度为3的鱼竿"
    reward = ('bait', 8, 3) # 奖励3个活虾

    def get_progress(self, context: UserContext) -> int:
        """如果拥有稀有度为3的鱼竿，则返回1，否则返回0。"""
        return 1 if 3 in context.owned_rod_rarities else 0

    def check(self, context: UserContext) -> bool:
        return 3 in context.owned_rod_rarities

class LegendaryAccessoryCollected(BaseAchievement):
    id = 18 # 对应原数据库中的 achievement_id
    name = "海神之佑"
    description = "获得一个稀有度为5的饰品"
    reward = ('premium_currency', 100, 1) # 假设奖励类型

    def get_progress(self, context: UserContext) -> int:
        """如果拥有稀有度为5的饰品，则返回1，否则返回0。"""
        return 1 if 5 in context.owned_accessory_rarities else 0

    def check(self, context: UserContext) -> bool:
        return 5 in context.owned_accessory_rarities