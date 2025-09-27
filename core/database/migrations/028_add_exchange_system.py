import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    添加交易所系统：
    - 大宗商品表：存储商品模板信息
    - 交易所价格历史表：存储每日价格
    - 用户大宗商品库存表：存储用户持有的商品
    - 用户表添加交易所账户状态字段
    """
    
    # 1. 在用户表中添加交易所账户状态字段
    cursor.execute("""
        ALTER TABLE users ADD COLUMN exchange_account_status INTEGER DEFAULT 0
    """)
    
    # 2. 创建大宗商品表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commodities (
            commodity_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        )
    """)
    
    # 3. 插入默认的大宗商品数据
    cursor.execute("""
        INSERT OR IGNORE INTO commodities (commodity_id, name, description) VALUES
        ('dried_fish', '鱼干', '稳健型标的，价格波动低'),
        ('fish_roe', '鱼卵', '高风险标的，价格波动极大'),
        ('fish_oil', '鱼油', '投机品，有概率触发事件导致价格大幅涨跌')
    """)
    
    # 4. 创建交易所价格历史表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_prices (
            price_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            commodity_id TEXT NOT NULL,
            price INTEGER NOT NULL,
            FOREIGN KEY (commodity_id) REFERENCES commodities(commodity_id),
            UNIQUE(date, commodity_id)
        )
    """)
    
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
    
    # 6. 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_prices_date ON exchange_prices(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_prices_commodity ON exchange_prices(commodity_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_commodities_user ON user_commodities(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_commodities_commodity ON user_commodities(commodity_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_commodities_expires ON user_commodities(expires_at)")


def down(cursor: sqlite3.Cursor):
    """回滚交易所系统"""
    cursor.execute("DROP TABLE IF EXISTS user_commodities")
    cursor.execute("DROP TABLE IF EXISTS exchange_prices")
    cursor.execute("DROP TABLE IF EXISTS commodities")
    
    # 注意：SQLite不支持直接删除列，所以这里不处理users表的exchange_account_status字段
    # 如果需要完全回滚，需要重建users表
