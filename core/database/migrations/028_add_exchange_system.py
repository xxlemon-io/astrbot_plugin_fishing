import sqlite3
from typing import List


def get_current_version() -> int:
    """
    返回此迁移脚本对应的版本号。
    """
    return 28


def get_migration_queries(db_version: int) -> List[str]:
    """
    根据传入的数据库版本号，返回需要执行的迁移SQL语句列表。
    """
    queries = []
    if db_version < 28:
        queries.extend([
            """
            -- 创建大宗商品表
            CREATE TABLE commodities (
                commodity_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT
            );
            """,
            """
            -- 插入默认的大宗商品数据
            INSERT INTO commodities (commodity_id, name, description) VALUES
            ('dried_fish', '鱼干', '稳健型标的，价格波动低'),
            ('fish_roe', '鱼卵', '高风险标的，价格波动极大'),
            ('fish_oil', '鱼油', '投机品，有概率触发事件导致价格大幅涨跌');
            """,
            """
            -- 创建交易所价格历史表
            CREATE TABLE exchange_prices (
                price_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                commodity_id TEXT NOT NULL,
                price INTEGER NOT NULL,
                FOREIGN KEY (commodity_id) REFERENCES commodities(commodity_id),
                UNIQUE(date, commodity_id)
            );
            """,
            """
            -- 创建用户大宗商品库存表
            CREATE TABLE user_commodities (
                instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                commodity_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                purchase_price INTEGER NOT NULL,
                purchased_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (commodity_id) REFERENCES commodities(commodity_id)
            );
            """,
            """
            -- 在 users 表中添加交易所账户状态
            ALTER TABLE users ADD COLUMN exchange_account_status INTEGER DEFAULT 0;
            """
        ])
    return queries


def upgrade(conn: sqlite3.Connection):
    """
    执行数据库升级。
    """
    c = conn.cursor()
    # 检查 users 表是否存在 exchange_account_status 列，如果不存在则添加
    c.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in c.fetchall()]
    if 'exchange_account_status' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN exchange_account_status INTEGER DEFAULT 0")

    # 获取当前版本并执行迁移
    c.execute("PRAGMA user_version")
    db_version = c.fetchone()[0]
    
    migration_queries = get_migration_queries(db_version)
    for query in migration_queries:
        c.execute(query)

    # 更新版本号
    c.execute(f"PRAGMA user_version = {get_current_version()}")
    conn.commit()
