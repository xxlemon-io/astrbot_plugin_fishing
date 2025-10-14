import sqlite3
from astrbot.api import logger

def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：为 users 表添加命运之-轮每日次数限制相关的字段。
    """
    logger.debug("正在执行 032_add_wof_daily_limit_fields: 为 users 表添加命运之-轮次数限制字段...")

    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]

        if 'wof_plays_today' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN wof_plays_today INTEGER DEFAULT 0")
            logger.info("成功为 users 表添加 'wof_plays_today' 字段。")
        else:
            logger.info("'wof_plays_today' 字段已存在，无需添加。")

        if 'last_wof_date' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_wof_date TEXT")
            logger.info("成功为 users 表添加 'last_wof_date' 字段。")
        else:
            logger.info("'last_wof_date' 字段已存在，无需添加。")

    except sqlite3.Error as e:
        logger.error(f"在迁移 032_add_wof_daily_limit_fields 期间发生错误: {e}")
        raise # <--- [关键修复] 补上这个缺失的 raise 语句