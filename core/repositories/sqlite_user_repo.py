import sqlite3
import threading
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..domain.models import User, TaxRecord
from .abstract_repository import AbstractUserRepository

class SqliteUserRepository(AbstractUserRepository):
    """用户数据仓储的SQLite实现"""

    def __init__(self, db_path: str):
        """
        初始化仓储。

        Args:
            db_path: SQLite数据库文件路径。
        """
        self.db_path = db_path
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """获取一个线程安全的数据库连接。"""
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            conn.row_factory = sqlite3.Row  # 返回字典形式的行
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.connection = conn
        return conn

    def _row_to_user(self, row: sqlite3.Row) -> Optional[User]:
        """将数据库行对象映射到User领域模型。"""
        if not row:
            return None

        # 处理可能为None的datetime字段
        def parse_datetime(dt_val):
            if isinstance(dt_val, datetime):
                return dt_val
            if isinstance(dt_val, str):
                try:
                    # 尝试多种格式以提高兼容性
                    return datetime.fromisoformat(dt_val)
                except ValueError:
                    return datetime.strptime(dt_val, "%Y-%m-%d %H:%M:%S")
            return None

        return User(
            user_id=row["user_id"],
            nickname=row["nickname"],
            coins=row["coins"],
            premium_currency=row["premium_currency"],
            total_fishing_count=row["total_fishing_count"],
            total_weight_caught=row["total_weight_caught"],
            total_coins_earned=row["total_coins_earned"],
            consecutive_login_days=row["consecutive_login_days"],
            fish_pond_capacity=row["fish_pond_capacity"],
            created_at=parse_datetime(row["created_at"]),
            equipped_rod_instance_id=row["equipped_rod_instance_id"],
            equipped_accessory_instance_id=row["equipped_accessory_instance_id"],
            current_title_id=row["current_title_id"],
            current_bait_id=row["current_bait_id"],
            bait_start_time=parse_datetime(row["bait_start_time"]),
            auto_fishing_enabled=bool(row["auto_fishing_enabled"]),
            last_fishing_time=parse_datetime(row["last_fishing_time"]),
            last_wipe_bomb_time=parse_datetime(row["last_wipe_bomb_time"]),
            last_steal_time=parse_datetime(row["last_steal_time"]),
            last_login_time=parse_datetime(row["last_login_time"]),
            fishing_zone_id=row["fishing_zone_id"],
        )

    def get_by_id(self, user_id: str) -> Optional[User]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return self._row_to_user(row)

    def check_exists(self, user_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None

    def add(self, user: User) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (user_id, nickname, coins, created_at) VALUES (?, ?, ?, ?)",
                (user.user_id, user.nickname, user.coins, user.created_at or datetime.now())
            )
            conn.commit()

    def update(self, user: User) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 服务层负责在更新前获取最新的用户状态
            cursor.execute("""
                UPDATE users SET
                    nickname = ?, coins = ?, premium_currency = ?,
                    total_fishing_count = ?, total_weight_caught = ?, total_coins_earned = ?,
                    consecutive_login_days = ?, fish_pond_capacity = ?,
                    equipped_rod_instance_id = ?, equipped_accessory_instance_id = ?,
                    current_title_id = ?, current_bait_id = ?, bait_start_time = ?,
                    auto_fishing_enabled = ?, last_fishing_time = ?, last_wipe_bomb_time = ?,
                    last_steal_time = ?, last_login_time = ?, last_stolen_at = ?, fishing_zone_id = ?
                WHERE user_id = ?
            """, (
                user.nickname, user.coins, user.premium_currency,
                user.total_fishing_count, user.total_weight_caught, user.total_coins_earned,
                user.consecutive_login_days, user.fish_pond_capacity,
                user.equipped_rod_instance_id, user.equipped_accessory_instance_id,
                user.current_title_id, user.current_bait_id, user.bait_start_time,
                user.auto_fishing_enabled, user.last_fishing_time, user.last_wipe_bomb_time,
                user.last_steal_time, user.last_login_time, user.last_stolen_at,
                user.fishing_zone_id,
                user.user_id
            ))
            conn.commit()

    def get_all_user_ids(self, auto_fishing_only: bool = False) -> List[str]:
        query = "SELECT user_id FROM users"
        params = []
        if auto_fishing_only:
            query += " WHERE auto_fishing_enabled = ?"
            params.append(1)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [row["user_id"] for row in cursor.fetchall()]

    def get_leaderboard_data(self, limit: int) -> List[Dict[str, Any]]:
        # 此方法返回一个DTO（数据传输对象），而不是领域模型，因为它需要多表连接
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    u.user_id, u.nickname, u.coins, u.total_fishing_count as fish_count,
                    t.name as title, r.name as fishing_rod, a.name as accessory
                FROM users u
                LEFT JOIN titles t ON u.current_title_id = t.title_id
                LEFT JOIN user_rods ur ON u.equipped_rod_instance_id = ur.rod_instance_id
                LEFT JOIN rods r ON ur.rod_id = r.rod_id
                LEFT JOIN user_accessories ua ON ua.user_id = u.user_id AND ua.is_equipped = 1
                LEFT JOIN accessories a ON ua.accessory_id = a.accessory_id
                ORDER BY u.coins DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_high_value_users(self, threshold: int) -> List[User]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE coins >= ?", (threshold,))
            return [self._row_to_user(row) for row in cursor.fetchall()]

    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """获取所有用户（分页）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
            return [self._row_to_user(row) for row in cursor.fetchall()]

    def get_users_count(self) -> int:
        """获取用户总数"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]

    def search_users(self, keyword: str, limit: int = 50, offset: int = 0) -> List[User]:
        """搜索用户（按用户ID或昵称，支持分页）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users 
                WHERE user_id LIKE ? OR nickname LIKE ? 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (f"%{keyword}%", f"%{keyword}%", limit, offset))
            return [self._row_to_user(row) for row in cursor.fetchall()]

    def get_search_users_count(self, keyword: str) -> int:
        """获取搜索结果的总数"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE user_id LIKE ? OR nickname LIKE ?",
                (f"%{keyword}%", f"%{keyword}%")
            )
            return cursor.fetchone()[0]

    def delete_user(self, user_id: str) -> bool:
        """删除用户（级联删除相关数据）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 删除用户相关的所有数据
                cursor.execute("DELETE FROM user_rods WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM user_accessories WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM user_fish_inventory WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM fishing_records WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM gacha_records WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM wipe_bomb_logs WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM market_listings WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM tax_records WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM user_achievement_progress WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM check_in_logs WHERE user_id = ?", (user_id,))
                # 最后删除用户
                cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                conn.commit()
                return cursor.rowcount > 0
            except Exception:
                conn.rollback()
                return False