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
    id = 33 # 对应原数据库中的 achievement_id
    name = "十倍奉还！"
    description = "在擦弹中获得10倍或以上奖励"
    target_value = 10.0
    reward = ("title", 6, 1) # 奖励 "擦弹之王" 称号

    def get_progress(self, context: UserContext) -> float:
        """返回用户擦弹获得过的最大倍率作为当前进度。"""
        return context.max_wipe_bomb_multiplier

    def check(self, context: UserContext) -> bool:
        return context.max_wipe_bomb_multiplier >= 10.0

class WipeBomb25xMultiplier(BaseAchievement):
    id = 34 # 对应原数据库中的 achievement_id
    name = "Lucky☆Star"
    description = "在擦弹中获得20倍或以上奖励"
    target_value = 25.0
    reward = ("title", 20, 1) # 奖励 "Lucky☆Star" 称号

    def get_progress(self, context: UserContext) -> float:
        """返回用户擦弹获得过的最大倍率作为当前进度。"""
        return context.max_wipe_bomb_multiplier

    def check(self, context: UserContext) -> bool:
        return context.max_wipe_bomb_multiplier >= 25.0

class WipeBomb50xMultiplier(BaseAchievement):
    id = 35 # 对应原数据库中的 achievement_id
    name = "計画通り"
    description = "在擦弹中获得50倍或以上奖励，一切尽在掌握!"
    target_value = 50.0
    reward = ("title", 21, 1) # 奖励 "計画通り" 称号

    def get_progress(self, context: UserContext) -> float:
        """返回用户擦弹获得过的最大倍率作为当前进度。"""
        return context.max_wipe_bomb_multiplier

    def check(self, context: UserContext) -> bool:
        return context.max_wipe_bomb_multiplier >= 50.0

class WipeBomb100xMultiplier(BaseAchievement):
    id = 36 # 对应原数据库中的 achievement_id
    name = "这就是我的逃跑路线！"
    description = "在擦弹中获得100倍或以上奖励"
    target_value = 100.0
    reward = ("title", 22, 1) # 奖励 "这就是我的逃跑路线！" 称号

    def get_progress(self, context: UserContext) -> float:
        """返回用户擦弹获得过的最大倍率作为当前进度。"""
        return context.max_wipe_bomb_multiplier

    def check(self, context: UserContext) -> bool:
        return context.max_wipe_bomb_multiplier >= 100.0

class WipeBomb150xMultiplier(BaseAchievement):
    id = 37 # 对应原数据库中的 achievement_id
    name = "超高校级的幸运"
    description = "在擦弹中获得150倍或以上奖励"
    target_value = 150.0
    reward = ("title", 23, 1) # 奖励 "超高校级的幸运" 称号

    def get_progress(self, context: UserContext) -> float:
        """返回用户擦弹获得过的最大倍率作为当前进度。"""
        return context.max_wipe_bomb_multiplier

    def check(self, context: UserContext) -> bool:
        return context.max_wipe_bomb_multiplier >= 150.0

class WipeBomb200xMultiplier(BaseAchievement):
    id = 38 # 对应原数据库中的 achievement_id
    name = "「 」"
    description = "在擦弹中获得200倍或以上奖励，NO GAME NO LIFE!"
    target_value = 200.0
    reward = ("title", 24, 1) # 奖励 "「 」" 称号

    def get_progress(self, context: UserContext) -> float:
        """返回用户擦弹获得过的最大倍率作为当前进度。"""
        return context.max_wipe_bomb_multiplier

    def check(self, context: UserContext) -> bool:
        return context.max_wipe_bomb_multiplier >= 200.0

class WipeBomb0002xMultiplier(BaseAchievement):
    id = 39 # 对应原数据库中的 achievement_id
    name = "杂鱼~杂鱼~"
    description = "在擦弹中获得0.002倍或以下奖励，杂鱼~杂鱼~"
    target_value = 0.002
    reward = ("title", 25, 1) # 奖励 "杂鱼~杂鱼~" 称号

    def get_progress(self, context: UserContext) -> float:
        """返回用户擦弹获得过的最大倍率作为当前进度。"""
        return context.min_wipe_bomb_multiplier

    def check(self, context: UserContext) -> bool:
        if context.min_wipe_bomb_multiplier is None:
            return False
        min_multiplier = context.min_wipe_bomb_multiplier
        return 0.0 < min_multiplier <= 0.002
