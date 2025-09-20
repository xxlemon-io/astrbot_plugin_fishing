import sqlite3
from astrbot.api import logger


def up(cursor: sqlite3.Cursor):
    logger.info("正在执行 012_update_gacha_pool_item_types: 更新 gacha_pool_items 表的 item_type 约束...")

    try:
        # 1. 重命名旧表
        cursor.execute("ALTER TABLE gacha_pool_items RENAME TO gacha_pool_items_old")

        # 2. 创建新表，并更新 CHECK 约束
        cursor.execute("""
            CREATE TABLE gacha_pool_items (
                gacha_pool_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                gacha_pool_id INTEGER NOT NULL,
                item_type TEXT NOT NULL CHECK (
                    item_type IN ('rod', 'accessory', 'bait', 'fish', 'coins', 'premium_currency', 'item')
                ),
                item_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                weight INTEGER NOT NULL CHECK (weight > 0),
                FOREIGN KEY (gacha_pool_id) REFERENCES gacha_pools(gacha_pool_id) ON DELETE CASCADE
            )
        """)

        # 3. 将旧表数据复制到新表
        cursor.execute("""
            INSERT INTO gacha_pool_items (
                gacha_pool_item_id, gacha_pool_id, item_type, item_id, quantity, weight
            )
            SELECT
                gacha_pool_item_id, gacha_pool_id, item_type, item_id, quantity, weight
            FROM gacha_pool_items_old
        """)

        # 4. 删除旧表
        cursor.execute("DROP TABLE gacha_pool_items_old")
        
        # 5. 重建索引
        cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_gacha_pool_items_pool_type ON gacha_pool_items(gacha_pool_id, item_type)")

        logger.info("012_update_gacha_pool_item_types: gacha_pool_items 表更新成功。")

    except sqlite3.OperationalError as e:
        # 如果过程中出现错误，尝试回滚
        if "no such table: gacha_pool_items" in str(e):
             logger.warning("gacha_pool_items 表不存在，可能是初次创建。跳过迁移。")
             # 如果原始表不存在，可能是在一个全新的数据库上运行，此时新表已经创建，可以直接返回
             pass
        elif "table gacha_pool_items already exists" in str(e):
            logger.warning("新表 gacha_pool_items 已存在，可能是重复执行迁移。正在尝试恢复...")
            # 尝试删除可能存在的旧的备份表
            cursor.execute("DROP TABLE IF EXISTS gacha_pool_items_old")
        else:
            logger.error(f"更新 gacha_pool_items 表时发生错误: {e}")
            # 尝试恢复
            cursor.execute("DROP TABLE IF EXISTS gacha_pool_items")
            cursor.execute("ALTER TABLE gacha_pool_items_old RENAME TO gacha_pool_items")
            raise e

def down(cursor: sqlite3.Cursor):
    logger.info("正在回滚 012_update_gacha_pool_item_types...")
    
    # 回滚操作与 up 操作类似，但是 CHECK 约束回到旧的状态
    cursor.execute("ALTER TABLE gacha_pool_items RENAME TO gacha_pool_items_new")

    cursor.execute("""
        CREATE TABLE gacha_pool_items (
            gacha_pool_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            gacha_pool_id INTEGER NOT NULL,
            item_type TEXT NOT NULL CHECK (
                item_type IN ('rod', 'accessory', 'bait', 'fish', 'coins', 'premium_currency')
            ),
            item_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            weight INTEGER NOT NULL CHECK (weight > 0),
            FOREIGN KEY (gacha_pool_id) REFERENCES gacha_pools(gacha_pool_id) ON DELETE CASCADE
        )
    """)
    
    # 复制数据，但只复制符合旧约束的
    cursor.execute("""
        INSERT INTO gacha_pool_items (
            gacha_pool_item_id, gacha_pool_id, item_type, item_id, quantity, weight
        )
        SELECT
            gacha_pool_item_id, gacha_pool_id, item_type, item_id, quantity, weight
        FROM gacha_pool_items_new
        WHERE item_type != 'item'
    """)

    cursor.execute("DROP TABLE gacha_pool_items_new")
    
    # 重建索引
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_gacha_pool_items_pool_type ON gacha_pool_items(gacha_pool_id, item_type)")
        
    logger.info("012_update_gacha_pool_item_types 回滚完成。")
