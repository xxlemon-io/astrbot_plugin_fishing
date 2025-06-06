class UserFishing:
    def __init__(self, user_id, nickname, coins):
        self.user_id = user_id
        self.nickname = nickname
        self.coins = coins
    def __str__(self):
        return f"UserFishing(user_id={self.user_id}, nickname={self.nickname}, coins={self.coins})"

# 定义鱼塘容量常量
POND_CAPACITY_PRIMARY = 480
POND_CAPACITY_MIDDLE = 999
POND_CAPACITY_ADVANCED = 9999
POND_CAPACITY_TOP = 99999