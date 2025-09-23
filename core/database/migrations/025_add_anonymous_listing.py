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
    # 添加 is_anonymous 字段，默认为 False（非匿名）
    _ensure_column(cursor, "market", "is_anonymous", "BOOLEAN DEFAULT 0")
    
    # 检查字段是否成功添加，如果添加成功则设置默认值
    cursor.execute("PRAGMA table_info(market)")
    cols = [row[1] for row in cursor.fetchall()]
    if "is_anonymous" in cols:
        # 为现有数据设置默认值（非匿名）
        # 注意：SQLite中BOOLEAN实际上是INTEGER，所以使用0和1
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
