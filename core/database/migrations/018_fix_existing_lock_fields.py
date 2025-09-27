import sqlite3

def up(cursor: sqlite3.Cursor):
    """
    修复现有数据的锁定字段问题
    确保所有现有的鱼竿和饰品都有 is_locked 字段
    """
    from astrbot.api import logger
    logger.info("正在执行 018_fix_existing_lock_fields: 修复现有数据的锁定字段...")
    
    # 检查 user_rods 表是否有 is_locked 字段
    cursor.execute("PRAGMA table_info(user_rods)")
    user_rods_columns = [column[1] for column in cursor.fetchall()]
    
    if 'is_locked' not in user_rods_columns:
        logger.info("user_rods 表缺少 is_locked 字段，正在添加...")
        cursor.execute("""
            ALTER TABLE user_rods ADD COLUMN is_locked INTEGER DEFAULT 0 CHECK (is_locked IN (0, 1))
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_rods_locked ON user_rods(user_id, is_locked)")
    else:
        logger.info("user_rods 表已有 is_locked 字段")
        # 确保现有数据的 is_locked 字段不是 NULL
        cursor.execute("UPDATE user_rods SET is_locked = 0 WHERE is_locked IS NULL")
    
    # 检查 user_accessories 表是否有 is_locked 字段
    cursor.execute("PRAGMA table_info(user_accessories)")
    user_accessories_columns = [column[1] for column in cursor.fetchall()]
    
    if 'is_locked' not in user_accessories_columns:
        logger.info("user_accessories 表缺少 is_locked 字段，正在添加...")
        cursor.execute("""
            ALTER TABLE user_accessories ADD COLUMN is_locked INTEGER DEFAULT 0 CHECK (is_locked IN (0, 1))
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_accessories_locked ON user_accessories(user_id, is_locked)")
    else:
        logger.info("user_accessories 表已有 is_locked 字段")
        # 确保现有数据的 is_locked 字段不是 NULL
        cursor.execute("UPDATE user_accessories SET is_locked = 0 WHERE is_locked IS NULL")
    
    cursor.connection.commit()
    logger.info("锁定字段修复完成")

def down(cursor: sqlite3.Cursor):
    """
    回滚：这个迁移不需要回滚，因为它只是修复数据
    """
    logger.info("018_fix_existing_lock_fields 不需要回滚")
    pass
