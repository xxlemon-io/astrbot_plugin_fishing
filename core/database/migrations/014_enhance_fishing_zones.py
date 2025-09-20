import sqlite3
import json


def up(cursor: sqlite3.Cursor):
    cursor.execute("ALTER TABLE fishing_zones ADD COLUMN configs TEXT")

    # 为现有区域添加默认配置
    default_configs = {
        1: {"rarity_distribution": [0.6, 0.3, 0.08, 0.02, 0]},
        2: {"rarity_distribution": [0.4, 0.3, 0.2, 0.09, 0.01]},
        3: {"rarity_distribution": [0.3, 0.2, 0.2, 0.2, 0.1]}
    }

    for zone_id, configs in default_configs.items():
        cursor.execute(
            "UPDATE fishing_zones SET configs = ? WHERE id = ?",
            (json.dumps(configs), zone_id)
        )

    # 从 015 合并过来的代码
    cursor.execute("ALTER TABLE fishing_zones ADD COLUMN is_active INTEGER DEFAULT 1")
    cursor.execute("ALTER TABLE fishing_zones ADD COLUMN available_from TEXT")
    cursor.execute("ALTER TABLE fishing_zones ADD COLUMN available_until TEXT")

    cursor.execute("""
        CREATE TABLE zone_fish_mapping (
            zone_id INTEGER,
            fish_id INTEGER,
            PRIMARY KEY (zone_id, fish_id),
            FOREIGN KEY (zone_id) REFERENCES fishing_zones(id) ON DELETE CASCADE,
            FOREIGN KEY (fish_id) REFERENCES fish(fish_id) ON DELETE CASCADE
        )
    """)


def down(cursor: sqlite3.Cursor):
    cursor.execute("DROP TABLE IF EXISTS zone_fish_mapping")

    # 创建一个新表，复制数据，然后删除旧表
    cursor.execute("""
        CREATE TABLE fishing_zones_new (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            daily_rare_fish_quota INTEGER NOT NULL,
            rare_fish_caught_today INTEGER NOT NULL DEFAULT 0
        )
    """)
    cursor.execute("""
        INSERT INTO fishing_zones_new (id, name, description, daily_rare_fish_quota, rare_fish_caught_today)
        SELECT id, name, description, daily_rare_fish_quota, rare_fish_caught_today FROM fishing_zones
    """)
    cursor.execute("DROP TABLE fishing_zones")
    cursor.execute("ALTER TABLE fishing_zones_new RENAME TO fishing_zones")
