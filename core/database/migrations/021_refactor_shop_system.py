import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    重构商店系统：实现 shops + shop_items 的简洁设计
    - shops: 商店表
    - shop_items: 商店商品表（包含成本、奖励、库存等信息）
    """
    from astrbot.api import logger
    logger.info("正在执行 021_refactor_shop_system: 重构商店系统...")

    # 1. 创建 shops 表
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shops (
            shop_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            shop_type TEXT NOT NULL DEFAULT 'normal' CHECK (shop_type IN ('normal','premium','limited')),
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            start_time DATETIME,  -- 开始日期时间
            end_time DATETIME,    -- 结束日期时间
            daily_start_time TIME,  -- 每日开始时间（如 09:00）
            daily_end_time TIME,    -- 每日结束时间（如 18:00）
            sort_order INTEGER DEFAULT 100 NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shops_active_time ON shops(is_active, start_time, end_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shops_type ON shops(shop_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shops_daily_time ON shops(daily_start_time, daily_end_time)")

    # 2. 创建 shop_items 表（商品基本信息）
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shop_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'general' NOT NULL,
            
            -- 库存和限购信息
            stock_total INTEGER,  -- NULL 表示无限库存
            stock_sold INTEGER DEFAULT 0 NOT NULL,
            per_user_limit INTEGER,  -- NULL 表示无限
            per_user_daily_limit INTEGER,  -- NULL 表示无限
            
            -- 状态和时间
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            start_time DATETIME,
            end_time DATETIME,
            sort_order INTEGER DEFAULT 100 NOT NULL,
            
            -- 时间戳
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id) ON DELETE CASCADE
        )
        """
    )
    
    # 3. 创建 shop_item_costs 表（支持多成本 + AND/OR 关系）
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shop_item_costs (
            cost_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            cost_type TEXT NOT NULL CHECK (cost_type IN ('coins','premium','item','fish')),
            cost_amount INTEGER NOT NULL CHECK (cost_amount > 0),
            cost_item_id INTEGER,  -- cost_type 为 'item' 或 'fish' 时使用
            cost_relation TEXT DEFAULT 'and' CHECK (cost_relation IN ('and', 'or')),  -- 成本关系：and=全部需要, or=多选一
            group_id INTEGER,  -- 用于分组，同一组内的成本是OR关系，不同组是AND关系
            FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE
        )
        """
    )
    
    # 4. 创建 shop_item_rewards 表（支持多奖励）
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shop_item_rewards (
            reward_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            reward_type TEXT NOT NULL CHECK (reward_type IN ('rod','accessory','bait','item','fish','coins')),
            reward_item_id INTEGER,  -- reward_type 为具体物品时使用
            reward_quantity INTEGER NOT NULL DEFAULT 1 CHECK (reward_quantity > 0),
            reward_refine_level INTEGER,  -- 精炼等级
            FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE
        )
        """
    )
    
    # 5. 创建购买记录表
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shop_purchase_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """
    )
    
    # 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_items_shop ON shop_items(shop_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_items_active_time ON shop_items(is_active, start_time, end_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_items_category ON shop_items(category)")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_item ON shop_item_costs(item_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_type ON shop_item_costs(cost_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_relation ON shop_item_costs(cost_relation)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_costs_group ON shop_item_costs(group_id)")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_rewards_item ON shop_item_rewards(item_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_item_rewards_type ON shop_item_rewards(reward_type)")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_purchase_user_item ON shop_purchase_records(user_id, item_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shop_purchase_time ON shop_purchase_records(timestamp)")

    logger.info("商店系统重构完成：shops + shop_items 设计")


def down(cursor: sqlite3.Cursor):
    """回滚：删除新的商店系统表"""
    logger.info("正在回滚 021_refactor_shop_system...")
    cursor.execute("DROP TABLE IF EXISTS shop_purchase_records")
    cursor.execute("DROP TABLE IF EXISTS shop_item_rewards")
    cursor.execute("DROP TABLE IF EXISTS shop_item_costs")
    cursor.execute("DROP TABLE IF EXISTS shop_items")
    cursor.execute("DROP TABLE IF EXISTS shops")
    logger.info("回滚完成")
