"""
迁移040：添加红包系统
创建红包系统相关表，包括红包表和红包领取记录表
"""

from astrbot.api import logger

def up(cursor):
    """创建红包系统表"""
    
    try:
        logger.info("[迁移040] 创建红包系统表")
        
        # 创建红包表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS red_packets (
                packet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                packet_type TEXT NOT NULL,
                total_amount INTEGER NOT NULL,
                total_count INTEGER NOT NULL,
                remaining_amount INTEGER NOT NULL,
                remaining_count INTEGER NOT NULL,
                password TEXT,
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                is_expired INTEGER DEFAULT 0
            )
        """)
        
        # 创建红包领取记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS red_packet_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                packet_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                claimed_at TIMESTAMP NOT NULL,
                FOREIGN KEY (packet_id) REFERENCES red_packets(packet_id)
            )
        """)
        
        # 创建索引以提升查询性能
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_red_packets_group 
            ON red_packets(group_id, is_expired)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_red_packet_records_packet 
            ON red_packet_records(packet_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_red_packet_records_user 
            ON red_packet_records(user_id, packet_id)
        """)
        
        logger.info("[迁移040] 红包系统表创建成功")
            
    except Exception as e:
        logger.error(f"[迁移040] 迁移失败: {e}")
        raise

def down(cursor):
    """回滚：删除红包系统表"""
    
    try:
        logger.info("[迁移040-回滚] 删除红包系统表")
        
        cursor.execute("DROP INDEX IF EXISTS idx_red_packet_records_user")
        cursor.execute("DROP INDEX IF EXISTS idx_red_packet_records_packet")
        cursor.execute("DROP INDEX IF EXISTS idx_red_packets_group")
        cursor.execute("DROP TABLE IF EXISTS red_packet_records")
        cursor.execute("DROP TABLE IF EXISTS red_packets")
        
        logger.info("[迁移040-回滚] 红包系统表删除成功")
            
    except Exception as e:
        logger.error(f"[迁移040-回滚] 回滚失败: {e}")
        raise
