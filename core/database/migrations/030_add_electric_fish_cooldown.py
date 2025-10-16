import sqlite3
from astrbot.api import logger

def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：为 users 表添加 last_electric_fish_time 字段。
    """
    logger.debug("正在执行 030_add_electric_fish_cooldown: 为 users 表添加电鱼冷却字段...")

    try:
        # 检查字段是否已存在，以确保脚本可重复运行
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]

        if 'last_electric_fish_time' not in columns:
            # 如果字段不存在，则添加它
            cursor.execute("""
                ALTER TABLE users ADD COLUMN last_electric_fish_time DATETIME
            """)
            logger.info("成功为 users 表添加 'last_electric_fish_time' 字段。")
        else:
            logger.info("'last_electric_fish_time' 字段已存在于 users 表中，无需添加。")

    except sqlite3.Error as e:
        logger.error(f"在迁移 030_add_electric_fish_cooldown 期间发生错误: {e}")
        # 抛出异常以可能停止启动过程
        raise