import sqlite3
from astrbot.api import logger


def up(cursor: sqlite3.Cursor):
    """
    新增道具模板表 items 与用户道具表 user_items。
    - items: 存放可在背包“道具栏”展示的道具模板（如消耗品、功能道具等）
    - user_items: 存放用户持有的道具数量
    """
    logger.info("正在执行 010_add_items_and_user_items: 创建 items 与 user_items 表...")

    # 道具模板表
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            rarity INTEGER NOT NULL DEFAULT 1,
            effect_description TEXT,
            cost INTEGER DEFAULT 0,
            is_consumable INTEGER DEFAULT 1,
            icon_url TEXT
        )
        """
    )

    # 用户道具表
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_items (
            user_id TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 0 CHECK (quantity >= 0),
            PRIMARY KEY (user_id, item_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
        )
        """
    )

    cursor.connection.commit()


