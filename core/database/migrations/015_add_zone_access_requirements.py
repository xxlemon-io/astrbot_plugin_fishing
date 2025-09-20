import sqlite3


def up(cursor: sqlite3.Cursor):
    # 为钓鱼区域添加通行证要求和钓鱼消耗字段
    cursor.execute("ALTER TABLE fishing_zones ADD COLUMN required_item_id INTEGER")
    cursor.execute("ALTER TABLE fishing_zones ADD COLUMN requires_pass BOOLEAN DEFAULT 0")
    cursor.execute("ALTER TABLE fishing_zones ADD COLUMN fishing_cost INTEGER DEFAULT 10")
    
    # 为现有区域设置默认值（区域1不需要通行证）
    cursor.execute("""
        UPDATE fishing_zones 
        SET required_item_id = NULL, 
            requires_pass = 0 
        WHERE id = 1
    """)
    
    # 为现有区域设置默认消耗（基于原有逻辑）
    # 区域1: 10金币，区域2: 60金币，区域3: 110金币，区域4: 160金币
    cursor.execute("""
        UPDATE fishing_zones 
        SET fishing_cost = 10 + (id - 1) * 50
    """)


def down(cursor: sqlite3.Cursor):
    # 删除添加的字段
    cursor.execute("ALTER TABLE fishing_zones DROP COLUMN required_item_id")
    cursor.execute("ALTER TABLE fishing_zones DROP COLUMN requires_pass")
    cursor.execute("ALTER TABLE fishing_zones DROP COLUMN fishing_cost")
