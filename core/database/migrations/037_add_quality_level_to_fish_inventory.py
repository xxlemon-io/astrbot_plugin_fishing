import sqlite3

from astrbot.api import logger


def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：为鱼类库存添加品质系统支持。
    
    改动内容：
    1. user_fish_inventory 表添加 quality_level 字段（0=普通，1=高品质）
    2. 调整主键为 (user_id, fish_id, quality_level)
    3. user_aquarium 表同样添加 quality_level 字段
    4. 迁移现有数据，全部标记为普通品质
    """
    logger.info("正在执行 037_add_quality_level_to_fish_inventory: 添加品质系统...")
    
    # === 第一部分：user_fish_inventory 表改造 ===
    
    # 1. 重命名旧表
    cursor.execute("ALTER TABLE user_fish_inventory RENAME TO user_fish_inventory_old")
    
    # 2. 创建新表（含 quality_level）
    cursor.execute("""
        CREATE TABLE user_fish_inventory (
            user_id TEXT NOT NULL,
            fish_id INTEGER NOT NULL,
            quality_level INTEGER DEFAULT 0 CHECK (quality_level IN (0, 1)),
            quantity INTEGER DEFAULT 0 CHECK (quantity >= 0),
            no_sell_until DATETIME,
            PRIMARY KEY (user_id, fish_id, quality_level),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (fish_id) REFERENCES fish(fish_id) ON DELETE CASCADE
        )
    """)
    
    # 3. 迁移数据（所有记录设为普通品质 quality_level=0）
    cursor.execute("""
        INSERT INTO user_fish_inventory (user_id, fish_id, quality_level, quantity, no_sell_until)
        SELECT user_id, fish_id, 0, quantity, no_sell_until 
        FROM user_fish_inventory_old
        WHERE quantity > 0
    """)
    
    # 4. 删除旧表
    cursor.execute("DROP TABLE user_fish_inventory_old")
    
    logger.info("user_fish_inventory 表改造完成")
    
    # === 第二部分：user_aquarium 表改造 ===
    
    # 1. 重命名旧表
    cursor.execute("ALTER TABLE user_aquarium RENAME TO user_aquarium_old")
    
    # 2. 创建新表（含 quality_level）
    cursor.execute("""
        CREATE TABLE user_aquarium (
            user_id TEXT NOT NULL,
            fish_id INTEGER NOT NULL,
            quality_level INTEGER DEFAULT 0 CHECK (quality_level IN (0, 1)),
            quantity INTEGER DEFAULT 0 CHECK (quantity >= 0),
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, fish_id, quality_level),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (fish_id) REFERENCES fish(fish_id) ON DELETE CASCADE
        )
    """)
    
    # 3. 迁移数据（所有记录设为普通品质 quality_level=0）
    cursor.execute("""
        INSERT INTO user_aquarium (user_id, fish_id, quality_level, quantity, added_at)
        SELECT user_id, fish_id, 0, quantity, added_at 
        FROM user_aquarium_old
        WHERE quantity > 0
    """)
    
    # 4. 删除旧表
    cursor.execute("DROP TABLE user_aquarium_old")
    
    logger.info("user_aquarium 表改造完成")
    logger.info("037_add_quality_level_to_fish_inventory 迁移完成！")


def down(cursor: sqlite3.Cursor):
    """
    回滚此迁移：移除品质系统，恢复原始结构。
    
    注意：高品质鱼会被合并到普通鱼中，品质信息会丢失。
    """
    logger.info("正在回滚 037_add_quality_level_to_fish_inventory...")
    
    # === 回滚 user_fish_inventory ===
    
    # 1. 重命名当前表
    cursor.execute("ALTER TABLE user_fish_inventory RENAME TO user_fish_inventory_new")
    
    # 2. 创建旧版表结构
    cursor.execute("""
        CREATE TABLE user_fish_inventory (
            user_id TEXT NOT NULL,
            fish_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 0 CHECK (quantity >= 0),
            no_sell_until DATETIME,
            PRIMARY KEY (user_id, fish_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (fish_id) REFERENCES fish(fish_id) ON DELETE CASCADE
        )
    """)
    
    # 3. 合并数据（不同品质的鱼合并成一条记录）
    cursor.execute("""
        INSERT INTO user_fish_inventory (user_id, fish_id, quantity, no_sell_until)
        SELECT user_id, fish_id, SUM(quantity), MAX(no_sell_until)
        FROM user_fish_inventory_new
        GROUP BY user_id, fish_id
        HAVING SUM(quantity) > 0
    """)
    
    # 4. 删除新表
    cursor.execute("DROP TABLE user_fish_inventory_new")
    
    # === 回滚 user_aquarium ===
    
    # 1. 重命名当前表
    cursor.execute("ALTER TABLE user_aquarium RENAME TO user_aquarium_new")
    
    # 2. 创建旧版表结构
    cursor.execute("""
        CREATE TABLE user_aquarium (
            user_id TEXT NOT NULL,
            fish_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 0 CHECK (quantity >= 0),
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, fish_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (fish_id) REFERENCES fish(fish_id) ON DELETE CASCADE
        )
    """)
    
    # 3. 合并数据
    cursor.execute("""
        INSERT INTO user_aquarium (user_id, fish_id, quantity, added_at)
        SELECT user_id, fish_id, SUM(quantity), MIN(added_at)
        FROM user_aquarium_new
        GROUP BY user_id, fish_id
        HAVING SUM(quantity) > 0
    """)
    
    # 4. 删除新表
    cursor.execute("DROP TABLE user_aquarium_new")
    
    logger.info("037_add_quality_level_to_fish_inventory 回滚完成")
