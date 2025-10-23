import random
from datetime import datetime, date, timedelta, timezone
from typing import List, Tuple, Any

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# 获取当前的UTC+8时间
def get_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))

def get_today() -> date:
    return get_now().date()

def get_last_reset_time(reset_hour: int = 0) -> datetime:
    """
    获取最近一次刷新时间点
    
    Args:
        reset_hour: 每日刷新的小时数（0-23），默认为0表示0点刷新
    
    Returns:
        最近一次刷新的时间点（datetime对象）
    
    Example:
        如果 reset_hour=6，当前时间是今天8点，返回今天6点
        如果 reset_hour=6，当前时间是今天5点，返回昨天6点
    """
    now = get_now()
    # 创建今天的刷新时间点
    today_reset = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
    
    # 如果当前时间已经过了今天的刷新时间点，返回今天的刷新时间点
    if now >= today_reset:
        return today_reset
    else:
        # 否则返回昨天的刷新时间点
        return today_reset - timedelta(days=1)

def get_fish_template(new_fish_list, coins_chance):
    """
    使用标准的加权随机算法从鱼类列表中选择一个模板。
    - 解决了旧算法中存在的边界问题和行为异常的Bug。
    - 逻辑清晰，行为可预测：价值越高的鱼，被选中的基础概率越大。
    - coins_chance > 0 时，会放大高价值鱼的概率优势。
    """
    # 边界情况处理：如果列表为空，返回None
    if not new_fish_list:
        return None
        
    # 边界情况处理：如果列表只有一个元素，直接返回，避免不必要的计算
    if len(new_fish_list) == 1:
        return new_fish_list[0]

    # 1. 为列表中的每一条鱼计算其抽选权重
    weights = []
    for fish in new_fish_list:
        # 保证基础权重至少为1，以防鱼的价值为0或负数
        base_weight = max(fish.base_value, 1)
        
        # 应用 coins_chance 加成。
        # (1 + coins_chance) 是一个简单的放大系数，确保了加成效果。
        # 例如，如果 coins_chance 是 0.5 (50%)，则权重会乘以 1.5
        final_weight = base_weight * (1 + coins_chance) 
        weights.append(final_weight)

    # 2. 使用Python标准库的 random.choices 函数进行加权随机抽样
    #   - new_fish_list: 从这个列表中抽样
    #   - weights: 对应的权重列表
    #   - k=1: 只抽取一个结果
    #   [0]：因为 choices 返回的是一个列表，我们取出其中的第一个（也是唯一一个）元素
    chosen_fish = random.choices(new_fish_list, weights=weights, k=1)[0]
    
    return chosen_fish

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