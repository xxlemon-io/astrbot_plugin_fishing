"""
迁移039：添加金币历史最高记录字段
添加 max_coins 字段到 users 表，用于追踪用户历史最高金币数
"""

from astrbot.api import logger

def up(cursor):
    """添加 max_coins 字段"""
    
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "max_coins" not in columns:
            logger.info("[迁移039] 添加 max_coins 字段到 users 表")
            
            # 添加 max_coins 字段，默认值为当前金币数
            cursor.execute("""
                ALTER TABLE users ADD COLUMN max_coins INTEGER DEFAULT 0
            """)
            
            # 将现有用户的 max_coins 初始化为当前金币数
            cursor.execute("""
                UPDATE users SET max_coins = coins WHERE max_coins < coins OR max_coins IS NULL
            """)
            
            logger.info("[迁移039] max_coins 字段添加成功")
        else:
            logger.info("[迁移039] max_coins 字段已存在，跳过")
            
    except Exception as e:
        logger.error(f"[迁移039] 迁移失败: {e}")
        raise

def down(cursor):
    """回滚：移除 max_coins 字段"""
    
    try:
        logger.info("[迁移039-回滚] 准备移除 max_coins 字段")
        
        # SQLite 不支持 DROP COLUMN，需要重建表
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "max_coins" in columns:
            # 获取除 max_coins 外的所有列
            columns.remove("max_coins")
            columns_str = ", ".join(columns)
            
            # 重建表（不包含 max_coins）
            cursor.execute(f"""
                CREATE TABLE users_backup AS 
                SELECT {columns_str}
                FROM users
            """)
            
            cursor.execute("DROP TABLE users")
            cursor.execute("ALTER TABLE users_backup RENAME TO users")
            
            logger.info("[迁移039-回滚] max_coins 字段移除成功")
        else:
            logger.info("[迁移039-回滚] max_coins 字段不存在，无需回滚")
            
    except Exception as e:
        logger.error(f"[迁移039-回滚] 回滚失败: {e}")
        raise
