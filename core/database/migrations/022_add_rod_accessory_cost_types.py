import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    添加鱼竿和饰品作为消耗类型支持
    """
    # 1. 删除现有的CHECK约束
    cursor.execute("PRAGMA table_info(shop_item_costs)")
    columns = cursor.fetchall()
    
    # 2. 重新创建表，添加rod和accessory支持
    cursor.execute("""
        CREATE TABLE shop_item_costs_new (
            cost_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            cost_type TEXT NOT NULL CHECK (cost_type IN ('coins','premium','item','fish','rod','accessory')),
            cost_amount INTEGER NOT NULL CHECK (cost_amount > 0),
            cost_item_id INTEGER,  -- cost_type 为具体物品时使用
            cost_relation TEXT DEFAULT 'and' CHECK (cost_relation IN ('and', 'or')),
            group_id INTEGER,
            FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE
        )
    """)
    
    # 3. 复制现有数据
    cursor.execute("""
        INSERT INTO shop_item_costs_new 
        SELECT * FROM shop_item_costs
    """)
    
    # 4. 删除旧表
    cursor.execute("DROP TABLE shop_item_costs")
    
    # 5. 重命名新表
    cursor.execute("ALTER TABLE shop_item_costs_new RENAME TO shop_item_costs")
    
    # 6. 重新创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_item ON shop_item_costs(item_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_type ON shop_item_costs(cost_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_relation ON shop_item_costs(cost_relation)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_group ON shop_item_costs(group_id)")


def down(cursor: sqlite3.Cursor):
    """
    回退：移除rod和accessory支持
    """
    # 1. 删除包含rod或accessory类型的成本记录
    cursor.execute("DELETE FROM shop_item_costs WHERE cost_type IN ('rod', 'accessory')")
    
    # 2. 重新创建表，移除rod和accessory支持
    cursor.execute("""
        CREATE TABLE shop_item_costs_new (
            cost_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            cost_type TEXT NOT NULL CHECK (cost_type IN ('coins','premium','item','fish')),
            cost_amount INTEGER NOT NULL CHECK (cost_amount > 0),
            cost_item_id INTEGER,
            cost_relation TEXT DEFAULT 'and' CHECK (cost_relation IN ('and', 'or')),
            group_id INTEGER,
            FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE
        )
    """)
    
    # 3. 复制现有数据
    cursor.execute("""
        INSERT INTO shop_item_costs_new 
        SELECT * FROM shop_item_costs
    """)
    
    # 4. 删除旧表
    cursor.execute("DROP TABLE shop_item_costs")
    
    # 5. 重命名新表
    cursor.execute("ALTER TABLE shop_item_costs_new RENAME TO shop_item_costs")
    
    # 6. 重新创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_item ON shop_item_costs(item_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_type ON shop_item_costs(cost_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_relation ON shop_item_costs(cost_relation)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_group ON shop_item_costs(group_id)")
