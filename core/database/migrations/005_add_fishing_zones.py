import sqlite3

def up(cursor: sqlite3.Cursor):
    cursor.execute("""
        CREATE TABLE fishing_zones (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            daily_rare_fish_quota INTEGER NOT NULL,
            rare_fish_caught_today INTEGER NOT NULL DEFAULT 0
        )
        """)

    zones_to_add = [
        (1, "区域一：新手港湾", "只能钓到0-4星鱼，4星鱼概率很低。", 50),
        (2, "区域二：深海峡谷", "4星鱼概率提升，有极小概率钓到5星鱼。", 2000),
        (3, "区域三：传说之海", "5星鱼概率大幅提升。", 500)
    ]

    cursor.executemany(
        "INSERT INTO fishing_zones (id, name, description, daily_rare_fish_quota) VALUES (?, ?, ?, ?)",
        zones_to_add
    )
    cursor.execute("ALTER TABLE users ADD COLUMN fishing_zone_id INTEGER DEFAULT 1")