import sqlite3
from astrbot.api import logger

def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：重构 baits 表，添加结构化效果列，并根据已有的 effect_description 填充新列的数据。
    """
    logger.info("正在执行 003_refactor_baits_table_with_data_migration: 重构 baits 表...")

    # 1. 安全地添加新列
    columns_to_add = {
        "success_rate_modifier": "REAL DEFAULT 0.0",
        "rare_chance_modifier": "REAL DEFAULT 0.0",
        "garbage_reduction_modifier": "REAL DEFAULT 0.0",
        "value_modifier": "REAL DEFAULT 1.0",
        "quantity_modifier": "REAL DEFAULT 1.0",
        "is_consumable": "INTEGER DEFAULT 1"
    }
    for col, col_type in columns_to_add.items():
        try:
            cursor.execute(f"ALTER TABLE baits ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                logger.debug(f"列 '{col}' 已存在，跳过添加。")
            else:
                raise e

    # 2. 读取所有现有的鱼饵描述
    cursor.execute("SELECT bait_id, effect_description FROM baits")
    all_baits = cursor.fetchall()

    # 3. 遍历并根据描述更新新列
    for bait_row in all_baits:
        bait_id, effect_desc = bait_row["bait_id"], bait_row["effect_description"]

        if not effect_desc:
            continue

        updates = {}
        desc_lower = effect_desc.lower()

        # 根据原仓库的逻辑和新设计的目标值进行映射
        if "提高所有鱼种上钩率" in desc_lower:
            updates["success_rate_modifier"] = 0.15
        elif "大幅提高钓鱼成功率" in desc_lower:
            updates["success_rate_modifier"] = 0.20
        elif "提高多种鱼上钩率" in desc_lower:
            updates["success_rate_modifier"] = 0.08
        elif "提高中小型鱼上钩率" in desc_lower:
            updates["success_rate_modifier"] = 0.05
        elif "略微提高钓鱼成功率" in desc_lower:
            updates["success_rate_modifier"] = 0.02

        if "显著提高稀有鱼几率" in desc_lower:
            updates["rare_chance_modifier"] = 0.03
        elif "大幅提高稀有鱼上钩率" in desc_lower:
            updates["rare_chance_modifier"] = 0.05
        elif "略微提高稀有鱼几率" in desc_lower:
            updates["rare_chance_modifier"] = 0.01

        if "降低钓上" in desc_lower and "垃圾" in desc_lower:
            updates["garbage_reduction_modifier"] = 0.5  # 降低50%的概率

        if "基础价值+10%" in effect_desc:
            updates["value_modifier"] = 1.1

        if "双倍数量" in effect_desc:
            updates["quantity_modifier"] = 2.0

        if "无消耗" in desc_lower:
            updates["is_consumable"] = 0

        # 如果有需要更新的字段，则执行UPDATE
        if updates:
            set_clauses = ", ".join([f"{key} = ?" for key in updates.keys()])
            params = list(updates.values())
            params.append(bait_id)

            cursor.execute(f"UPDATE baits SET {set_clauses} WHERE bait_id = ?", tuple(params))

    logger.info("已根据 effect_description 成功迁移数据到新列。")

