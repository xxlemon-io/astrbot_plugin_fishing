import sqlite3


def _to_base36(n: int) -> str:
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return "0"
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = []
    while n:
        n, rem = divmod(n, 36)
        out.append(digits[rem])
    return "".join(reversed(out))


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, ddl: str):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def up(cursor: sqlite3.Cursor):
    """
    为 user_rods 与 user_accessories 增加 display_code 短码列，并为历史数据回填：
    - 鱼竿：R + base36(rod_instance_id)
    - 饰品：A + base36(accessory_instance_id)
    均使用大写并建立唯一索引。
    """
    from astrbot.api import logger
    logger.info("执行 023_add_display_code_to_equipment: 添加 display_code 并回填...")

    # 1) 添加列
    _ensure_column(cursor, "user_rods", "display_code", "display_code TEXT")
    _ensure_column(cursor, "user_accessories", "display_code", "display_code TEXT")

    # 2) 为历史数据回填
    # user_rods
    try:
        cursor.execute("SELECT rod_instance_id FROM user_rods WHERE display_code IS NULL OR display_code = ''")
        missing_rods = [row[0] for row in cursor.fetchall()]
        for rid in missing_rods:
            code = "R" + _to_base36(int(rid))
            cursor.execute(
                "UPDATE user_rods SET display_code = ? WHERE rod_instance_id = ?",
                (code, rid),
            )
    except Exception:
        pass

    # user_accessories
    try:
        cursor.execute("SELECT accessory_instance_id FROM user_accessories WHERE display_code IS NULL OR display_code = ''")
        missing_acc = [row[0] for row in cursor.fetchall()]
        for aid in missing_acc:
            code = "A" + _to_base36(int(aid))
            cursor.execute(
                "UPDATE user_accessories SET display_code = ? WHERE accessory_instance_id = ?",
                (code, aid),
            )
    except Exception:
        pass

    # 3) 创建唯一索引
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_rods_display_code ON user_rods(display_code)")
    except Exception:
        pass
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_accessories_display_code ON user_accessories(display_code)")
    except Exception:
        pass

    logger.info("023_add_display_code_to_equipment: 回填完成。")


def down(cursor: sqlite3.Cursor):
    """
    回滚：仅移除唯一索引（SQLite 删除列较复杂，保持列存在）。
    """
    try:
        cursor.execute("DROP INDEX IF EXISTS idx_user_rods_display_code")
    except Exception:
        pass
    try:
        cursor.execute("DROP INDEX IF EXISTS idx_user_accessories_display_code")
    except Exception:
        pass
    logger.info("023_add_display_code_to_equipment: 索引已移除（列保留）。")


