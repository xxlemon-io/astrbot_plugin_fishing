# 迁移脚本 034: 为 users 表添加每日擦弹次数追踪字段

import sqlite3
from astrbot.api import logger

def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：为 users 表添加 wipe_bomb_attempts_today 和 last_wipe_bomb_date 字段。
    """
    logger.debug("正在执行 036_add_user_wipe_bomb_daily_tracking: 添加每日擦弹追踪字段...")

    try:
        # 检查 users 表的现有列
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]

        # 1. 添加每日擦弹次数字段
        if 'wipe_bomb_attempts_today' not in columns:
            # NOT NULL 和 DEFAULT 0 确保该字段始终有有效值，避免后续处理 NULL 的麻烦
            cursor.execute("ALTER TABLE users ADD COLUMN wipe_bomb_attempts_today INTEGER NOT NULL DEFAULT 0")
            logger.info("成功为 users 表添加 'wipe_bomb_attempts_today' 字段。")
        else:
            logger.info("'wipe_bomb_attempts_today' 字段已存在，无需添加。")

        # 2. 添加上次擦弹日期的字段
        if 'last_wipe_bomb_date' not in columns:
            # TEXT 类型用于存储 'YYYY-MM-DD' 格式的日期字符串，DEFAULT NULL 表示新用户或从未玩过的用户没有记录
            cursor.execute("ALTER TABLE users ADD COLUMN last_wipe_bomb_date TEXT DEFAULT NULL")
            logger.info("成功为 users 表添加 'last_wipe_bomb_date' 字段。")
        else:
            logger.info("'last_wipe_bomb_date' 字段已存在，无需添加。")

    except sqlite3.Error as e:
        logger.error(f"在迁移 036_add_user_wipe_bomb_daily_tracking 期间发生错误: {e}")
        raise