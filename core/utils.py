import random
from datetime import datetime, date, timedelta, timezone

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

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

def calculate_after_refine(before_value: float, refine_level: int, rarity: int = None) -> float:
    """
    计算经过精炼后的值
    根据装备稀有度使用不同的精炼加成比例
    
    精炼加成比例：
    - 1-2★装备: 15%/级 (让低星装备有更多成长空间)
    - 3★装备: 15%/级
    - 4★装备: 12%/级
    - 5★装备: 8%/级
    - 6★装备: 5%/级
    - 7★+装备: 3%/级
    
    Args:
        before_value: 精炼前的值
        refine_level: 精炼等级 (1-10)
        rarity: 装备稀有度 (如果不提供则使用默认10%)
    
    Returns:
        精炼后的值
    """
    # 如果没有提供稀有度，使用旧的10%逻辑保持兼容性
    if rarity is None:
        bonus_per_level = 0.1
    else:
        # 基于稀有度的差异化加成
        if rarity <= 3:
            bonus_per_level = 0.15  # 15%/级
        elif rarity == 4:
            bonus_per_level = 0.12  # 12%/级
        elif rarity == 5:
            bonus_per_level = 0.08  # 8%/级
        elif rarity == 6:
            bonus_per_level = 0.05  # 5%/级
        else:  # 7星+
            bonus_per_level = 0.03  # 3%/级
    
    # 计算总加成
    effective_refine_level = refine_level - 1 if refine_level <= 10 else 9
    total_bonus = bonus_per_level * effective_refine_level
    
    # 应用加成
    if before_value < 1:
        return before_value * (1 + total_bonus)
    return (before_value - 1) * (1 + total_bonus) + 1