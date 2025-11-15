import sqlite3
import threading
from typing import Optional, List
from datetime import datetime

# 导入抽象基类和领域模型
from .abstract_repository import AbstractAchievementRepository, UserAchievementProgress
from ..domain.models import Achievement

class SqliteAchievementRepository(AbstractAchievementRepository):
    """成就数据仓储的SQLite实现"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.connection = conn
        return conn

    def _row_to_achievement(self, row: sqlite3.Row) -> Optional[Achievement]:
        if not row:
            return None
        data = dict(row)
        data["is_repeatable"] = bool(data.get("is_repeatable", 0))
        return Achievement(**data)

    def get_all_achievements(self) -> List[Achievement]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM achievements ORDER BY achievement_id")
            return [self._row_to_achievement(row) for row in cursor.fetchall()]

    def get_user_progress(self, user_id: str) -> UserAchievementProgress:
        """获取指定用户的所有成就进度"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT achievement_id, current_progress, completed_at
                FROM user_achievement_progress
                WHERE user_id = ?
            """, (user_id,))
            rows = cursor.fetchall()
            progress = {}
            for row in rows:
                achievement_id = row["achievement_id"]
                progress[achievement_id] = {
                    "progress": row["current_progress"],
                    "completed_at": row["completed_at"]
                }
            return progress

    def update_user_progress(self, user_id: str, achievement_id: int, progress: int,
                             completed_at: Optional[datetime]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. 检查记录是否已存在
            cursor.execute(
                "SELECT completed_at FROM user_achievement_progress WHERE user_id = ? AND achievement_id = ?",
                (user_id, achievement_id))
            record = cursor.fetchone()

            if record:
                # 2. 如果记录存在，则执行 UPDATE
                # 仅当记录中原来的 completed_at 为空时，才更新它，确保完成时间只记录一次
                db_completed_at = record["completed_at"]
                final_completed_at = db_completed_at if db_completed_at else completed_at

                cursor.execute("""
                    UPDATE user_achievement_progress
                    SET current_progress = ?, completed_at = ?
                    WHERE user_id = ? AND achievement_id = ?
                """, (progress, final_completed_at, user_id, achievement_id))
            else:
                # 3. 如果记录不存在，则执行 INSERT
                cursor.execute("""
                    INSERT INTO user_achievement_progress (user_id, achievement_id, current_progress, completed_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, achievement_id, progress, completed_at))

            conn.commit()

    def grant_title_to_user(self, user_id: str, title_id: int) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO user_titles (user_id, title_id, unlocked_at) VALUES (?, ?, ?)", (user_id, title_id, datetime.now()))
            conn.commit()

    def revoke_title_from_user(self, user_id: str, title_id: int) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_titles WHERE user_id = ? AND title_id = ?", (user_id, title_id))
            conn.commit()

    # --- 新增的成就检查方法实现 ---

    def get_user_unique_fish_count(self, user_id: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT fish_id) FROM user_fish_inventory WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0

    def get_user_garbage_count(self, user_id: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 垃圾定义：稀有度为1且基础价值<=2
            cursor.execute("""
                SELECT SUM(ufi.quantity) FROM user_fish_inventory ufi
                JOIN fish f ON ufi.fish_id = f.fish_id
                WHERE ufi.user_id = ? AND f.rarity = 1 AND f.base_value <= 2
            """, (user_id,))
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0

    def has_caught_heavy_fish(self, user_id: str, weight: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM fishing_records WHERE user_id = ? AND weight >= ? LIMIT 1", (user_id, weight))
            return cursor.fetchone() is not None

    def has_wipe_bomb_multiplier(self, user_id: str, multiplier: float) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM wipe_bomb_log WHERE user_id = ? AND reward_multiplier >= ? LIMIT 1", (user_id, multiplier))
            return cursor.fetchone() is not None

    def has_item_of_rarity(self, user_id: str, item_type: str, rarity: int) -> bool:
        query = ""
        if item_type == "rod":
            query = """
                SELECT 1 FROM user_rods ur JOIN rods r ON ur.rod_id = r.rod_id
                WHERE ur.user_id = ? AND r.rarity = ? LIMIT 1
            """
        elif item_type == "accessory":
            query = """
                SELECT 1 FROM user_accessories ua JOIN accessories a ON ua.accessory_id = a.accessory_id
                WHERE ua.user_id = ? AND a.rarity = ? LIMIT 1
            """
        else:
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id, rarity))
            return cursor.fetchone() is not None
