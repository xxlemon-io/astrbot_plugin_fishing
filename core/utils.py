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
        move_rate = random.random() <= coins_chance
        if move_rate:
            return sorted_fish_list[min(max_move + 1, len(sorted_fish_list) - 1)]
        return sorted_fish_list[max_move]
    else:
        return sorted_fish_list[random_index]

def calculate_after_refine(before_value: float, refine_level: int) -> float:
    """
    计算经过精炼后的值
    精炼公式：value * (1 + 0.1 * refine_level)
    """
    if before_value < 1:
        return before_value * (1 + 0.1 * (refine_level - 1 if refine_level < 5 else 5))
    return (before_value - 1) * (1 + 0.1 * (refine_level - 1 if refine_level < 5 else 5)) + 1