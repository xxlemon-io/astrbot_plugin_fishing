import sqlite3

def up(cursor: sqlite3.Cursor):
    # 在 user_rods 和 user_accessories 表中增加一列 refine_level
    cursor.execute("""
        ALTER TABLE user_rods ADD COLUMN refine_level INTEGER DEFAULT 1
    """)
    cursor.execute("""
        ALTER TABLE user_accessories ADD COLUMN refine_level INTEGER DEFAULT 1
    """)
