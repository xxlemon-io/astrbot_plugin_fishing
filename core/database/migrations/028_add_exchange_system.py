import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    添加交易所系统：
    - 大宗商品表：存储商品模板信息
    - 交易所价格历史表：存储每日价格
    - 用户大宗商品库存表：存储用户持有的商品
    - 用户表添加交易所账户状态字段（如果不存在）
    """
    
    # 1. 在用户表中添加交易所账户状态字段（如果不存在）
    try:
        cursor.execute("""
            ALTER TABLE users ADD COLUMN exchange_account_status INTEGER DEFAULT 0
        """)
        print("  - 已添加 users.exchange_account_status 字段")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("  - users.exchange_account_status 字段已存在，跳过")
        else:
            raise
    
    # 2. 创建大宗商品表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commodities (
            commodity_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        )
    """)
    print("  - 已创建 commodities 表")
    
    # 3. 插入默认的大宗商品数据
    cursor.execute("""
        INSERT OR IGNORE INTO commodities (commodity_id, name, description) VALUES
        ('dried_fish', '鱼干', '稳健型标的，价格波动低'),
        ('fish_roe', '鱼卵', '高风险标的，价格波动极大'),
        ('fish_oil', '鱼油', '投机品，有概率触发事件导致价格大幅涨跌')
    """)
    print("  - 已插入默认大宗商品数据")
    
    # 4. 创建交易所价格历史表（支持每日多次更新）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_prices (
            price_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            commodity_id TEXT NOT NULL,
            price INTEGER NOT NULL,
            update_type TEXT DEFAULT 'auto',
            created_at TEXT NOT NULL,
            FOREIGN KEY (commodity_id) REFERENCES commodities(commodity_id)
        )
    """)
    print("  - 已创建 exchange_prices 表（支持每日多次更新）")
    
    # 5. 创建用户大宗商品库存表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_commodities (
            instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            commodity_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            purchase_price INTEGER NOT NULL,
            purchased_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (commodity_id) REFERENCES commodities(commodity_id) ON DELETE CASCADE
        )
    """)
    print("  - 已创建 user_commodities 表")
    
    # 6. 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_prices_date_commodity ON exchange_prices(date, commodity_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_prices_created_at ON exchange_prices(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_commodities_user ON user_commodities(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_commodities_commodity ON user_commodities(commodity_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_commodities_expires ON user_commodities(expires_at)")
    print("  - 已创建相关索引")


def down(cursor: sqlite3.Cursor):
    """回滚交易所系统"""
    cursor.execute("DROP TABLE IF EXISTS user_commodities")
    cursor.execute("DROP TABLE IF EXISTS exchange_prices")
    cursor.execute("DROP TABLE IF EXISTS commodities")
    
    # 注意：SQLite不支持直接删除列，所以这里不处理users表的exchange_account_status字段
    # 如果需要完全回滚，需要重建users表
