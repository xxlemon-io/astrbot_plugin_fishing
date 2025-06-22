from .base import BaseAchievement, UserContext

class TotalCoinsEarned1M(BaseAchievement):
    id = 12 # 对应原数据库中的 achievement_id
    name = "富可敌国"
    description = "累计赚取1,000,000金币"
    target_value = 1000000
    reward = ("title", 5, 1) # 奖励 "百万富翁" 称号

    def get_progress(self, context: UserContext) -> int:
        """返回用户累计获得的金币数作为当前进度。"""
        return context.user.total_coins_earned

    def check(self, context: UserContext) -> bool:
        return context.user.total_coins_earned >= 1000000

class WipeBomb10xMultiplier(BaseAchievement):
    id = 15 # 对应原数据库中的 achievement_id
    name = "十倍奉还！"
    description = "在擦弹中获得10倍或以上奖励"
    target_value = 10.0
    reward = ("title", 6, 1) # 奖励 "擦弹之王" 称号

    def get_progress(self, context: UserContext) -> float:
        """返回用户擦弹获得过的最大倍率作为当前进度。"""
        return context.max_wipe_bomb_multiplier

    def check(self, context: UserContext) -> bool:
        return context.max_wipe_bomb_multiplier >= 10.0
