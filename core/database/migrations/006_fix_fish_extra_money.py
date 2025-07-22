import sqlite3

def up(cursor: sqlite3.Cursor):
    # 在 users_fish_inventory 表中增加一列 extra_value_multiplier
    cursor.execute("""
        ALTER TABLE user_fish_inventory ADD COLUMN extra_value_multiplier REAL DEFAULT 0.0
    """)
    # users_fish_inventory 中把 quantity 的值 乘以 1.0 作为 extra_value_multiplier 的初始值
    cursor.execute("""
        UPDATE user_fish_inventory SET extra_value_multiplier = quantity * 1.0
    """)
    # 结束事务
    cursor.connection.commit()

