import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    在 market_listings 表中添加 expires_at 列
    """
    # 检查 market_listings 表是否存在 expires_at 列，如果不存在则添加
    cursor.execute("PRAGMA table_info(market_listings)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'expires_at' not in columns:
        cursor.execute("ALTER TABLE market_listings ADD COLUMN expires_at TEXT")


def down(cursor: sqlite3.Cursor):
    """回滚：删除 expires_at 列"""
    # 注意：SQLite不支持直接删除列，所以这里不处理
    # 如果需要完全回滚，需要重建market_listings表
    pass
