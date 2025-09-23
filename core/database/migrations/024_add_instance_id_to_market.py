import sqlite3


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, ddl: str):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def up(cursor: sqlite3.Cursor):
    """
    为 market 表添加 item_instance_id 字段，用于存储实例ID以便显示短码
    """
    # 添加 item_instance_id 字段
    _ensure_column(cursor, "market", "item_instance_id", "INTEGER")
    
    # 检查字段是否成功添加，如果添加成功则设置默认值
    cursor.execute("PRAGMA table_info(market)")
    cols = [row[1] for row in cursor.fetchall()]
    if "item_instance_id" in cols:
        # 为现有数据设置默认值（暂时设为NULL，因为无法确定原始实例ID）
        cursor.execute("UPDATE market SET item_instance_id = NULL WHERE item_instance_id IS NULL")


def down(cursor: sqlite3.Cursor):
    """
    回滚：移除 item_instance_id 字段
    """
    # SQLite不支持直接删除列，需要重建表
    cursor.execute("""
        CREATE TABLE market_backup AS SELECT 
            market_id, user_id, item_type, item_id, quantity, price, 
            listed_at, expires_at, refine_level, seller_nickname, 
            item_name, item_description
        FROM market
    """)
    
    cursor.execute("DROP TABLE market")
    cursor.execute("ALTER TABLE market_backup RENAME TO market")
