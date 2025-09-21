import sqlite3


def up(cursor: sqlite3.Cursor):
    """移除鱼类稀有度的CHECK约束，支持任意星级"""
    
    # 创建新的fish表，移除稀有度限制
    cursor.execute("""
        CREATE TABLE fish_new (
            fish_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            rarity INTEGER NOT NULL CHECK (rarity >= 1),
            base_value INTEGER NOT NULL,
            min_weight INTEGER NOT NULL CHECK (min_weight >= 0),
            max_weight INTEGER NOT NULL CHECK (max_weight > min_weight),
            icon_url TEXT
        )
    """)
    
    # 复制旧表数据到新表
    cursor.execute("""
        INSERT INTO fish_new (fish_id, name, description, rarity, base_value, min_weight, max_weight, icon_url)
        SELECT fish_id, name, description, rarity, base_value, min_weight, max_weight, icon_url
        FROM fish
    """)
    
    # 删除旧表
    cursor.execute("DROP TABLE fish")
    
    # 重命名新表
    cursor.execute("ALTER TABLE fish_new RENAME TO fish")


def down(cursor: sqlite3.Cursor):
    """回滚：恢复鱼类稀有度的1-5限制"""
    
    # 创建旧的fish表，恢复稀有度限制
    cursor.execute("""
        CREATE TABLE fish_old (
            fish_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            rarity INTEGER NOT NULL CHECK (rarity >= 1 AND rarity <= 5),
            base_value INTEGER NOT NULL,
            min_weight INTEGER NOT NULL CHECK (min_weight >= 0),
            max_weight INTEGER NOT NULL CHECK (max_weight > min_weight),
            icon_url TEXT
        )
    """)
    
    # 复制数据，但只复制1-5星的鱼（6+星的鱼会被丢弃）
    cursor.execute("""
        INSERT INTO fish_old (fish_id, name, description, rarity, base_value, min_weight, max_weight, icon_url)
        SELECT fish_id, name, description, rarity, base_value, min_weight, max_weight, icon_url
        FROM fish
        WHERE rarity <= 5
    """)
    
    # 删除当前表
    cursor.execute("DROP TABLE fish")
    
    # 重命名表
    cursor.execute("ALTER TABLE fish_old RENAME TO fish")
