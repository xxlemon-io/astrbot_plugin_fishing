from astrbot.api import logger

import sqlite3

def up(cursor: sqlite3.Cursor):
    """
    升级数据库: 清除所有用户的成就进度。
    这是一个破坏性操作，会删除 `user_achievement_progress` 表中的所有行。
    """
    # 步骤 1: 删除表中的所有数据
    cursor.execute("DELETE FROM user_achievement_progress;")
    logger.info("已删除 `user_achievement_progress` 表中的所有数据。")

    # 步骤 2: 重置该表的自增 ID 序列 (此操作对 SQLite 有效)
    # 这样新进度将从 ID 1 重新开始
    cursor.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'user_achievement_progress';")
    logger.info("已重置 `user_achievement_progress` 表的自增序列。")

    logger.info("应用迁移: 004_clear_user_achievement_progress")
