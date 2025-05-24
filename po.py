class UserFishing:
    def __init__(self, user_id, nickname, coins):
        self.user_id = user_id
        self.nickname = nickname
        self.coins = coins
    def __str__(self):
        return f"UserFishing(user_id={self.user_id}, nickname={self.nickname}, coins={self.coins})"