import sqlite3


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, ddl: str):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def up(cursor: sqlite3.Cursor):
    """
    为 market 表添加 is_anonymous 字段，用于支持匿名上架功能
    """
    # 检查是否已经存在错误的 BOOLEAN 字段
    cursor.execute("PRAGMA table_info(market)")
    cols = [row[1] for row in cursor.fetchall()]
    
    if "BOOLEAN" in cols and "is_anonymous" not in cols:
        # 修复错误的字段名：将 BOOLEAN 重命名为 is_anonymous
        from astrbot.api import logger
        logger.info("发现错误的 BOOLEAN 字段，正在修复为 is_anonymous...")
        
        # 创建备份表，包含正确的字段名
        cursor.execute("""
            CREATE TABLE market_backup AS SELECT 
                market_id, user_id, item_type, item_id, quantity, price, 
                listed_at, expires_at, refine_level, seller_nickname, 
                item_name, item_description, item_instance_id,
                BOOLEAN AS is_anonymous
            FROM market
        """)
        
        # 删除原表并重命名备份表
        cursor.execute("DROP TABLE market")
        cursor.execute("ALTER TABLE market_backup RENAME TO market")
        
        # 重新创建索引
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_market_id 
            ON market(market_id)
        """)
        
        logger.info("字段名修复完成")
    else:
        # 正常添加 is_anonymous 字段
        _ensure_column(cursor, "market", "is_anonymous", "INTEGER DEFAULT 0")
        
        # 检查字段是否成功添加，如果添加成功则设置默认值
        cursor.execute("PRAGMA table_info(market)")
        cols = [row[1] for row in cursor.fetchall()]
        if "is_anonymous" in cols:
            # 为现有数据设置默认值（非匿名）
            cursor.execute("UPDATE market SET is_anonymous = 0 WHERE is_anonymous IS NULL")


def down(cursor: sqlite3.Cursor):
    """
    回滚：移除 is_anonymous 字段
    """
    # SQLite不支持直接删除列，需要重建表
    cursor.execute("""
        CREATE TABLE market_backup AS SELECT 
            market_id, user_id, item_type, item_id, quantity, price, 
            listed_at, expires_at, refine_level, seller_nickname, 
            item_name, item_description, item_instance_id
        FROM market
    """)
    
    cursor.execute("DROP TABLE market")
    cursor.execute("ALTER TABLE market_backup RENAME TO market")
