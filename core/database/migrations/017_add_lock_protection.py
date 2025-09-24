import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    为鱼竿和饰品添加锁定保护功能
    """
    
    # 为 user_rods 表添加 is_locked 字段
    cursor.execute("""
        ALTER TABLE user_rods ADD COLUMN is_locked INTEGER DEFAULT 0 CHECK (is_locked IN (0, 1))
    """)
    
    # 为 user_accessories 表添加 is_locked 字段
    cursor.execute("""
        ALTER TABLE user_accessories ADD COLUMN is_locked INTEGER DEFAULT 0 CHECK (is_locked IN (0, 1))
    """)
    
    # 创建索引以提高查询性能
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_rods_locked ON user_rods(user_id, is_locked)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_accessories_locked ON user_accessories(user_id, is_locked)")
    
    cursor.connection.commit()


def down(cursor: sqlite3.Cursor):
    """
    回滚：移除锁定保护字段
    """
    
    # SQLite不支持直接删除列，需要重建表
    # 重建 user_rods 表（移除 is_locked 字段）
    cursor.execute("""
        CREATE TABLE user_rods_backup AS 
        SELECT rod_instance_id, user_id, rod_id, obtained_at, current_durability, is_equipped, refine_level
        FROM user_rods
    """)
    
    cursor.execute("DROP TABLE user_rods")
    cursor.execute("ALTER TABLE user_rods_backup RENAME TO user_rods")
    
    # 重建 user_accessories 表（移除 is_locked 字段）
    cursor.execute("""
        CREATE TABLE user_accessories_backup AS 
        SELECT accessory_instance_id, user_id, accessory_id, obtained_at, is_equipped, refine_level
        FROM user_accessories
    """)
    
    cursor.execute("DROP TABLE user_accessories")
    cursor.execute("ALTER TABLE user_accessories_backup RENAME TO user_accessories")
    
    # 重新创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_rods_user ON user_rods(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_accessories_user ON user_accessories(user_id)")
    
    cursor.connection.commit()
