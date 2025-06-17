from .base import BaseAchievement, UserContext


class TotalFishCount100(BaseAchievement):
    id = 2
    name = "小有所成"
    description = "累计钓到100条鱼"
    target_value = 100
    reward = ('coins', 500, 1)

    def get_progress(self, context: UserContext) -> int:
        """返回用户总钓鱼数作为当前进度。"""
        return context.user.total_fishing_count

    def check(self, context: UserContext) -> bool:
        # 使用 self.target_value 进行判断
        return context.user.total_fishing_count >= self.target_value


class TotalFishCount1000(BaseAchievement):
    id = 3
    name = "百竿不空"
    description = "累计钓到1000条鱼"
    target_value = 1000
    reward = ('title', 3, 1)  # 奖励 "钓鱼大师" 称号

    def get_progress(self, context: UserContext) -> int:
        """返回用户总钓鱼数作为当前进度。"""
        return context.user.total_fishing_count

    def check(self, context: UserContext) -> bool:
        return context.user.total_fishing_count >= self.target_value


class TotalWeight10000kg(BaseAchievement):
    id = 30
    name = "初露锋芒"
    description = "累计钓鱼总重量达到10,000公斤"
    target_value = 10000 * 1000  # 目标值统一使用g作为单位
    reward = ('title', 16, 1)

    def get_progress(self, context: UserContext) -> int:
        """返回用户总钓鱼重量作为当前进度。"""
        return context.user.total_weight_caught

    def check(self, context: UserContext) -> bool:
        return context.user.total_weight_caught >= self.target_value


class HeavyFishCaught(BaseAchievement):
    id = 32
    name = "庞然大物"
    description = "单次钓上重量超过100公斤的鱼"
    target_value = True  # 对于布尔类型的检查，目标值可以设为True
    reward = ('bait', 14, 1)

    def get_progress(self, context: UserContext) -> int:
        """对于布尔类型的成就，返回1代表已完成，0代表未完成。"""
        return 1 if context.has_heavy_fish else 0

    def check(self, context: UserContext) -> bool:
        return context.has_heavy_fish is self.target_value
