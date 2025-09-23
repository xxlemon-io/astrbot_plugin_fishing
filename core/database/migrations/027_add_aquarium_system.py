import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    添加水族箱系统：
    - 用户水族箱表：存储用户水族箱中的鱼
    - 用户表添加水族箱容量字段
    - 水族箱升级配置表
    """
    
    # 1. 在用户表中添加水族箱容量字段
    cursor.execute("""
        ALTER TABLE users ADD COLUMN aquarium_capacity INTEGER DEFAULT 50
    """)
    
    # 2. 创建用户水族箱表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_aquarium (
            user_id TEXT NOT NULL,
            fish_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 0 CHECK (quantity >= 0),
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, fish_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (fish_id) REFERENCES fish(fish_id) ON DELETE CASCADE
        )
    """)
    
    # 3. 创建水族箱升级配置表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aquarium_upgrades (
            upgrade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            level INTEGER NOT NULL UNIQUE,
            capacity INTEGER NOT NULL,
            cost_coins INTEGER NOT NULL,
            cost_premium INTEGER DEFAULT 0,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 4. 插入默认的水族箱升级配置
    upgrades = [
        (1, 50, 0, 0, "初始水族箱容量"),
        (2, 100, 10000, 0, "升级到100容量"),
        (3, 150, 25000, 0, "升级到150容量"),
        (4, 200, 50000, 0, "升级到200容量"),
        (5, 300, 100000, 0, "升级到300容量"),
        (6, 500, 200000, 0, "升级到500容量"),
        (7, 750, 500000, 0, "升级到750容量"),
        (8, 1000, 1000000, 0, "升级到1000容量"),
        (9, 1500, 2000000, 0, "升级到1500容量"),
        (10, 2000, 5000000, 0, "升级到2000容量"),
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO aquarium_upgrades (level, capacity, cost_coins, cost_premium, description)
        VALUES (?, ?, ?, ?, ?)
    """, upgrades)
    
    # 5. 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_aquarium_user ON user_aquarium(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_aquarium_fish ON user_aquarium(fish_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_aquarium_upgrades_level ON aquarium_upgrades(level)")


def down(cursor: sqlite3.Cursor):
    """回滚水族箱系统"""
    cursor.execute("DROP TABLE IF EXISTS user_aquarium")
    cursor.execute("DROP TABLE IF EXISTS aquarium_upgrades")
    
    # 注意：SQLite不支持直接删除列，所以这里不处理users表的aquarium_capacity字段
    # 如果需要完全回滚，需要重建users表
