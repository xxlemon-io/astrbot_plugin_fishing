import sqlite3
from astrbot.api import logger


def up(cursor: sqlite3.Cursor):
    """
    为道具系统增加效果与增益功能
    - items: 新增 effect_type 和 effect_payload 字段
    - 新增 user_buffs 表，用于记录用户的增益效果
    """
    logger.info("正在执行 011_add_item_effects_and_buffs: 更新 items 表并创建 user_buffs 表...")

    # 1. 更新 items 表
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN effect_type TEXT")
        cursor.execute("ALTER TABLE items ADD COLUMN effect_payload TEXT")
    except sqlite3.OperationalError as e:
        # 兼容重复执行脚本的情况
        if "duplicate column name" in str(e):
            logger.warning("items 表中已存在 effect_type 或 effect_payload 字段，跳过添加。")
        else:
            raise e

    # 2. 创建 user_buffs 表
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_buffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            buff_type TEXT NOT NULL,
            payload TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """
    )
    # 为 user_id 和 buff_type 创建索引以提高查询效率
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_buffs_user_id ON user_buffs(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_buffs_expires_at ON user_buffs(expires_at)")


    cursor.connection.commit()
