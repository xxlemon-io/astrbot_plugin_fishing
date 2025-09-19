def up(cursor):
    # 添加限时开放字段
    cursor.execute("""
        ALTER TABLE gacha_pools ADD COLUMN is_limited_time INTEGER DEFAULT 0
    """)
    cursor.execute("""
        ALTER TABLE gacha_pools ADD COLUMN open_until TEXT
    """)


