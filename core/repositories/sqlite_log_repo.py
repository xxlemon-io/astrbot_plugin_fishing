import sqlite3
import threading
from typing import Optional, List, Dict
from datetime import date, datetime, timedelta, timezone
# 导入抽象基类和领域模型
from .abstract_repository import AbstractLogRepository
from ..domain.models import FishingRecord, GachaRecord, WipeBombLog, TaxRecord

class SqliteLogRepository(AbstractLogRepository):
    """日志类数据仓储的SQLite实现"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        # 定义UTC+8时区
        self.UTC8 = timezone(timedelta(hours=8))

    def _get_connection(self) -> sqlite3.Connection:
        """获取一个线程安全的数据库连接。"""
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.connection = conn
        return conn

    # --- 私有映射辅助方法 ---
    def _row_to_fishing_record(self, row: sqlite3.Row) -> Optional[FishingRecord]:
        if not row:
            return None
        # 数据库中的 is_king_size 是 INTEGER，需要转为 bool
        data = dict(row)
        data["is_king_size"] = bool(data.get("is_king_size", 0))
        return FishingRecord(**data)

    def _row_to_gacha_record(self, row: sqlite3.Row) -> Optional[GachaRecord]:
        if not row:
            return None
        return GachaRecord(**row)

    def _row_to_wipe_bomb_log(self, row: sqlite3.Row) -> Optional[WipeBombLog]:
        if not row:
            return None
        return WipeBombLog(**row)

    def _row_to_tax_record(self, row: sqlite3.Row) -> Optional[TaxRecord]:
        if not row:
            return None
        return TaxRecord(**row)

    # --- Fishing Log Methods ---
    def add_fishing_record(self, record: FishingRecord) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fishing_records (
                    user_id, fish_id, weight, value, rod_instance_id,
                    accessory_instance_id, bait_id, timestamp, is_king_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.user_id, record.fish_id, record.weight, record.value,
                record.rod_instance_id, record.accessory_instance_id,
                record.bait_id, record.timestamp or datetime.now(self.UTC8),
                1 if record.is_king_size else 0
            ))
            conn.commit()
            return cursor.rowcount > 0


    def get_unlocked_fish_ids(self, user_id: str) -> Dict[int, datetime]:
        """
        获取指定用户所有钓到过的鱼类ID集合，以及对应的首次捕获时间。

        返回:
            Dict[int, datetime]: 键为鱼类ID，值为首次捕获时间
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fish_id, MIN(timestamp) as first_caught_time
                FROM fishing_records
                WHERE user_id = ?
                GROUP BY fish_id
            """, (user_id,))
            rows = cursor.fetchall()
            return {row["fish_id"]: row["first_caught_time"] for row in rows}
    def get_fishing_records(self, user_id: str, limit: int) -> List[FishingRecord]:
        with self._get_connection() as conn:
            # 为了简化返回，这里不连接获取名称，表现层可以按需从ItemTemplateRepository获取
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM fishing_records
                WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?
            """, (user_id, limit))
            return [self._row_to_fishing_record(row) for row in cursor.fetchall()]

    # --- Gacha Log Methods ---
    def add_gacha_record(self, record: GachaRecord) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO gacha_records (
                    user_id, gacha_pool_id, item_type, item_id,
                    item_name, quantity, rarity, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.user_id, record.gacha_pool_id, record.item_type,
                record.item_id, record.item_name, record.quantity,
                record.rarity, record.timestamp or datetime.now(self.UTC8)
            ))
            conn.commit()

    def get_gacha_records(self, user_id: str, limit: int) -> List[GachaRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM gacha_records
                WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?
            """, (user_id, limit))
            return [self._row_to_gacha_record(row) for row in cursor.fetchall()]

    # --- Wipe Bomb Log Methods ---
    # 存储时转为 UTC
    def add_wipe_bomb_log(self, log: WipeBombLog) -> None:
        timestamp = log.timestamp or datetime.now(self.UTC8)
        # 如果 timestamp 是 naive datetime，附加 UTC+8 时区
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=self.UTC8)
        # 确保存储为 UTC 时间字符串
        utc_timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO wipe_bomb_log
                (user_id, contribution_amount, reward_multiplier, reward_amount, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (log.user_id, log.contribution_amount, log.reward_multiplier,
                  log.reward_amount, utc_timestamp))
            conn.commit()

    # 查询时考虑时区
    def get_wipe_bomb_log_count_today(self, user_id: str) -> int:
        # 获取 UTC+8 的今天的开始和结束时间点（转为 UTC）
        today_start = datetime.now(self.UTC8).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # 转为 UTC 时间，移除时区信息
        utc_start = today_start.astimezone(timezone.utc).replace(tzinfo=None)
        utc_end = today_end.astimezone(timezone.utc).replace(tzinfo=None)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM wipe_bomb_log
                WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
            """, (user_id, utc_start, utc_end))
            result = cursor.fetchone()
            return result[0] if result else 0

    # --- Check-in Log Methods ---
    def add_check_in(self, user_id: str, check_in_date: date) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO check_ins (user_id, check_in_date) VALUES (?, ?)",
                (user_id, check_in_date)
            )
            conn.commit()

    def has_checked_in(self, user_id: str, check_in_date: date) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM check_ins WHERE user_id = ? AND check_in_date = ?",
                (user_id, check_in_date)
            )
            return cursor.fetchone() is not None

    # --- Tax Log Methods ---
    def add_tax_record(self, record: TaxRecord) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO taxes
                    (user_id, tax_amount, tax_rate, original_amount, balance_after, tax_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record.user_id, record.tax_amount, record.tax_rate,
                record.original_amount, record.balance_after,
                record.tax_type, record.timestamp or datetime.now(self.UTC8)
            ))
            conn.commit()

    def get_wipe_bomb_logs(self, user_id: str, limit: int = 10) -> List[WipeBombLog]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM wipe_bomb_log
                WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?
            """, (user_id, limit))
            return [self._row_to_wipe_bomb_log(row) for row in cursor.fetchall()]

    def get_tax_records(self, user_id: str, limit: int = 10) -> List[TaxRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM taxes
                WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?
            """, (user_id, limit))
            return [self._row_to_tax_record(row) for row in cursor.fetchall()]

    def get_max_wipe_bomb_multiplier(self, user_id: str) -> float:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(reward_multiplier) FROM wipe_bomb_log
                WHERE user_id = ?
            """, (user_id,))
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0.0
