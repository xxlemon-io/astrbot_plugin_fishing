# 迁移脚本 033: 为 users 表添加永久的擦弹统计字段

import sqlite3
from astrbot.api import logger

def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：为 users 表添加 max_wipe_bomb_multiplier 和 min_wipe_bomb_multiplier 字段。
    """
    logger.debug("正在执行 035_add_user_wipe_bomb_stats: 添加用户擦弹统计字段...")

    try:
        # 检查 users 表的现有列
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]

        # 添加生涯最大倍率字段
        if 'max_wipe_bomb_multiplier' not in columns:
            # DEFAULT 0.0 确保现有用户该字段不为 NULL
            cursor.execute("ALTER TABLE users ADD COLUMN max_wipe_bomb_multiplier REAL DEFAULT 0.0")
            logger.info("成功为 users 表添加 'max_wipe_bomb_multiplier' 字段。")
        else:
            logger.info("'max_wipe_bomb_multiplier' 字段已存在，无需添加。")

        # 添加生涯最小倍率字段
        if 'min_wipe_bomb_multiplier' not in columns:
            # DEFAULT NULL 因为 0 可能是一个有效值，而 NULL 表示从未有过记录
            cursor.execute("ALTER TABLE users ADD COLUMN min_wipe_bomb_multiplier REAL DEFAULT NULL")
            logger.info("成功为 users 表添加 'min_wipe_bomb_multiplier' 字段。")
        else:
            logger.info("'min_wipe_bomb_multiplier' 字段已存在，无需添加。")

    except sqlite3.Error as e:
        logger.error(f"在迁移 035_add_user_wipe_bomb_stats 期间发生错误: {e}")
        raise