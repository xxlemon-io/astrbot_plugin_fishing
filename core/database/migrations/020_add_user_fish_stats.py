import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    新增用户鱼类统计表，用于图鉴与个人纪录聚合：
    - first_caught_at / last_caught_at
    - max_weight / min_weight
    - total_caught / total_weight
    主键：(user_id, fish_id)
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_fish_stats (
            user_id TEXT NOT NULL,
            fish_id INTEGER NOT NULL,
            first_caught_at DATETIME,
            last_caught_at DATETIME,
            max_weight INTEGER NOT NULL,
            min_weight INTEGER NOT NULL,
            total_caught INTEGER NOT NULL DEFAULT 0,
            total_weight INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, fish_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (fish_id) REFERENCES fish(fish_id) ON DELETE RESTRICT
        )
        """
    )

    # 辅助索引
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_fish_stats_user ON user_fish_stats(user_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_fish_stats_fish ON user_fish_stats(fish_id)"
    )

    # 历史数据回填：从 fishing_records 聚合写入 user_fish_stats
    cursor.execute(
        """
        INSERT OR IGNORE INTO user_fish_stats (
            user_id, fish_id, first_caught_at, last_caught_at, max_weight, min_weight, total_caught, total_weight
        )
        SELECT
            user_id,
            fish_id,
            MIN(timestamp) AS first_caught_at,
            MAX(timestamp) AS last_caught_at,
            MAX(weight) AS max_weight,
            MIN(weight) AS min_weight,
            COUNT(*) AS total_caught,
            COALESCE(SUM(weight), 0) AS total_weight
        FROM fishing_records
        GROUP BY user_id, fish_id
        """
    )


def down(cursor: sqlite3.Cursor):
    cursor.execute("DROP TABLE IF EXISTS user_fish_stats")


