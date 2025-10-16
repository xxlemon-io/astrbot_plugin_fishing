import sqlite3
from astrbot.api import logger

def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：为 users 表添加命运之轮功能所需的所有字段。
    """
    logger.debug("正在执行 031_add_wheel_of_fate_fields: 为 users 表添加命运之轮字段...")

    try:
        # 检查现有列，避免重复添加
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]

        # 定义所有需要添加的字段及其类型
        fields_to_add = [
            ('in_wheel_of_fate', 'BOOLEAN'),
            ('wof_current_level', 'INTEGER'),
            ('wof_current_prize', 'INTEGER'),
            ('wof_entry_fee', 'INTEGER'),
            ('last_wof_play_time', 'DATETIME'),
            ('wof_last_action_time', 'DATETIME')
        ]

        # 循环检查并添加每一个缺失的字段
        for field_name, field_type in fields_to_add:
            if field_name not in columns:
                cursor.execute(f"""
                    ALTER TABLE users ADD COLUMN {field_name} {field_type}
                """)
                logger.info(f"成功为 users 表添加 '{field_name}' 字段。")
            else:
                logger.info(f"'{field_name}' 字段已存在于 users 表中，无需添加。")

    except sqlite3.Error as e:
        logger.error(f"在迁移 031_add_wheel_of_fate_fields 期间发生错误: {e}")
        raise