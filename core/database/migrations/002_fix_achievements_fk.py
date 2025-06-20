import sqlite3


def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：移除 user_achievement_progress 表中对 achievements 表的无效外键。
    """
    # SQLite 不支持直接用 ALTER TABLE 删除外键，因此需要重建表。

    # 1. 将旧表重命名，作为临时备份
    cursor.execute("ALTER TABLE user_achievement_progress RENAME TO _user_achievement_progress_old")

    # 2. 创建一个具有正确结构的新表（没有外键约束）
    cursor.execute("""
        CREATE TABLE user_achievement_progress (
            user_id TEXT NOT NULL,
            achievement_id INTEGER NOT NULL,
            current_progress INTEGER DEFAULT 0,
            completed_at DATETIME,
            claimed_at DATETIME,
            PRIMARY KEY (user_id, achievement_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # 3. 将旧表中的数据复制到新表中
    cursor.execute("""
        INSERT INTO user_achievement_progress (
            user_id, achievement_id, current_progress, completed_at, claimed_at
        )
        SELECT
            user_id, achievement_id, current_progress, completed_at, claimed_at
        FROM _user_achievement_progress_old
    """)

    # 4. 删除旧的备份表
    cursor.execute("DROP TABLE _user_achievement_progress_old")

# def down(cursor: sqlite3.Cursor):
#     """回滚此迁移"""
#     pass
