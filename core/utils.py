import random
from datetime import datetime, date, timedelta, timezone

# 获取当前的UTC+8时间
def get_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))

def get_today() -> date:
    return get_now().date()

def get_fish_template(new_fish_list, coins_chance):
    sorted_fish_list = sorted(new_fish_list, key=lambda x: x.base_value, reverse=True)
    random_index = random.randint(0, len(sorted_fish_list) - 1)
    if coins_chance > 0:
        max_move = random_index
        move_steps = int(max_move * min(coins_chance, 1.0))
        final_index = max(0, random_index - move_steps)
        return sorted_fish_list[final_index]
    else:
        return sorted_fish_list[random_index]
