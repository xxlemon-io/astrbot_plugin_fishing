import sqlite3
from astrbot.api import logger

def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：为 users 表添加骰宝游戏的冷却时间字段。
    """
    logger.debug("正在执行 033_add_sicbo_cooldown_field: 为 users 表添加骰宝冷却字段...")

    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]

        if 'last_sicbo_time' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_sicbo_time DATETIME")
            logger.info("成功为 users 表添加 'last_sicbo_time' 字段。")
        else:
            logger.info("'last_sicbo_time' 字段已存在，无需添加。")

    except sqlite3.Error as e:
        logger.error(f"在迁移 033_add_sicbo_cooldown_field 期间发生错误: {e}")
        raise