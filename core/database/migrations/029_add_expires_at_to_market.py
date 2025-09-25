import sqlite3
from typing import List


def get_current_version() -> int:
    """
    返回此迁移脚本对应的版本号。
    """
    return 29


def get_migration_queries(db_version: int) -> List[str]:
    """
    根据传入的数据库版本号，返回需要执行的迁移SQL语句列表。
    """
    queries = []
    if db_version < 29:
        queries.append(
            """
            -- 在 market_listings 表中添加 expires_at 列
            ALTER TABLE market_listings ADD COLUMN expires_at TEXT;
            """
        )
    return queries


def upgrade(conn: sqlite3.Connection):
    """
    执行数据库升级。
    """
    c = conn.cursor()
    # 检查 market_listings 表是否存在 expires_at 列，如果不存在则添加
    c.execute("PRAGMA table_info(market_listings)")
    columns = [row[1] for row in c.fetchall()]
    if 'expires_at' not in columns:
        c.execute("ALTER TABLE market_listings ADD COLUMN expires_at TEXT")

    # 获取当前版本并执行迁移
    c.execute("PRAGMA user_version")
    db_version = c.fetchone()[0]
    
    migration_queries = get_migration_queries(db_version)
    for query in migration_queries:
        c.execute(query)

    # 更新版本号
    c.execute(f"PRAGMA user_version = {get_current_version()}")
    conn.commit()
