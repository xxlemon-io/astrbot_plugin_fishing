import sqlite3

def up(cursor: sqlite3.Cursor):
    """在 market 表中新增一列 refine_level"""
    cursor.execute("""
        ALTER TABLE market ADD COLUMN refine_level INTEGER DEFAULT 1
    """)