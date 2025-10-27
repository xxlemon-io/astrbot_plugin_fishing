import sqlite3
import threading
from typing import Optional, List, Dict
from datetime import date, datetime, timedelta, timezone
# 导入抽象基类和领域模型
from .abstract_repository import AbstractLogRepository
from ..domain.models import FishingRecord, GachaRecord, WipeBombLog, TaxRecord, UserFishStat

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

    def _row_to_user_fish_stat(self, row: sqlite3.Row) -> Optional[UserFishStat]:
        if not row:
            return None
        data = dict(row)
        return UserFishStat(**data)

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
            # 1) 写入本次钓鱼记录
            cursor.execute(
                """
                INSERT INTO fishing_records (
                    user_id, fish_id, weight, value, rod_instance_id,
                    accessory_instance_id, bait_id, timestamp, is_king_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.user_id,
                    record.fish_id,
                    record.weight,
                    record.value,
                    record.rod_instance_id,
                    record.accessory_instance_id,
                    record.bait_id,
                    record.timestamp or datetime.now(self.UTC8),
                    1 if record.is_king_size else 0,
                ),
            )

            # 1.5) 更新用户鱼类聚合统计（UPSERT）
            now_ts = record.timestamp or datetime.now(self.UTC8)
            cursor.execute(
                """
                INSERT INTO user_fish_stats (
                    user_id, fish_id, first_caught_at, last_caught_at, max_weight, min_weight, total_caught, total_weight
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(user_id, fish_id) DO UPDATE SET
                    last_caught_at = excluded.last_caught_at,
                    max_weight = CASE WHEN excluded.max_weight > max_weight THEN excluded.max_weight ELSE max_weight END,
                    min_weight = CASE WHEN excluded.min_weight < min_weight THEN excluded.min_weight ELSE min_weight END,
                    total_caught = total_caught + 1,
                    total_weight = total_weight + excluded.total_weight
                """,
                (
                    record.user_id,
                    record.fish_id,
                    now_ts,
                    now_ts,
                    record.weight,
                    record.weight,
                    record.weight,
                ),
            )

            # 2) 仅保留当前用户最近10条记录（按时间倒序，时间相同按record_id倒序）
            cursor.execute(
                """
                DELETE FROM fishing_records
                WHERE user_id = ?
                  AND record_id NOT IN (
                    SELECT record_id FROM fishing_records
                    WHERE user_id = ?
                    ORDER BY timestamp DESC, record_id DESC
                    LIMIT 50
                  )
                """,
                (record.user_id, record.user_id),
            )

            # 3) 清理30天前的历史记录（全局）
            cutoff_time = datetime.now(self.UTC8) - timedelta(days=30)
            cursor.execute(
                """
                DELETE FROM fishing_records
                WHERE timestamp < ?
                """,
                (cutoff_time,),
            )

            conn.commit()
            return True


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
            # 1) 写入抽卡记录
            cursor.execute(
                """
                INSERT INTO gacha_records (
                    user_id, gacha_pool_id, item_type, item_id,
                    item_name, quantity, rarity, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.user_id,
                    record.gacha_pool_id,
                    record.item_type,
                    record.item_id,
                    record.item_name,
                    record.quantity,
                    record.rarity,
                    record.timestamp or datetime.now(self.UTC8),
                ),
            )

            # 2) 仅保留当前用户最近10条抽卡记录
            cursor.execute(
                """
                DELETE FROM gacha_records
                WHERE user_id = ?
                  AND record_id NOT IN (
                    SELECT record_id FROM gacha_records
                    WHERE user_id = ?
                    ORDER BY timestamp DESC, record_id DESC
                    LIMIT 50
                  )
                """,
                (record.user_id, record.user_id),
            )

            # 3) 清理30天前的抽卡记录（全局）
            cutoff_time = datetime.now(self.UTC8) - timedelta(days=30)
            cursor.execute(
                """
                DELETE FROM gacha_records
                WHERE timestamp < ?
                """,
                (cutoff_time,),
            )

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

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1) 写入擦弹日志
            cursor.execute(
                """INSERT INTO wipe_bomb_log
                (user_id, contribution_amount, reward_multiplier, reward_amount, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (log.user_id, log.contribution_amount, log.reward_multiplier, log.reward_amount, timestamp),
            )

            # 2) 仅保留当前用户最近10条擦弹日志
            cursor.execute(
                """
                DELETE FROM wipe_bomb_log
                WHERE user_id = ?
                  AND log_id NOT IN (
                    SELECT log_id FROM wipe_bomb_log
                    WHERE user_id = ?
                    ORDER BY timestamp DESC, log_id DESC
                    LIMIT 50
                  )
                """,
                (log.user_id, log.user_id),
            )

            # 3) 清理30天前的擦弹日志（全局）
            cutoff_time = datetime.now(self.UTC8) - timedelta(days=30)
            cursor.execute(
                """
                DELETE FROM wipe_bomb_log
                WHERE timestamp < ?
                """,
                (cutoff_time,),
            )

            conn.commit()

    # 查询时考虑时区
    def get_wipe_bomb_log_count_today(self, user_id: str) -> int:
        # 获取 UTC+8 的今天的开始和结束时间点
        today_start = datetime.now(self.UTC8).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM wipe_bomb_log
                WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
                  AND contribution_amount > 0
            """, (user_id, today_start, today_end))
            result = cursor.fetchone()
            return result[0] if result else 0

    # --- Check-in Log Methods ---
    def add_check_in(self, user_id: str, check_in_date: date) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1) 写入签到记录
            cursor.execute(
                "INSERT INTO check_ins (user_id, check_in_date) VALUES (?, ?)",
                (user_id, check_in_date),
            )

            # 2) 仅保留当前用户最近10条签到记录（按日期倒序）
            cursor.execute(
                """
                DELETE FROM check_ins
                WHERE user_id = ?
                  AND check_in_date NOT IN (
                    SELECT check_in_date FROM check_ins
                    WHERE user_id = ?
                    ORDER BY check_in_date DESC
                    LIMIT 50
                  )
                """,
                (user_id, user_id),
            )

            # 3) 清理30天前的签到记录（全局）
            cutoff_date = (datetime.now(self.UTC8) - timedelta(days=30)).date()
            cursor.execute(
                """
                DELETE FROM check_ins
                WHERE check_in_date < ?
                """,
                (cutoff_date,),
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

    def add_log(self, user_id: str, log_type: str, message: str) -> None:
        """添加一条通用日志"""
        # 由于 fishing_records 表有外键约束，我们使用一个简单的日志表
        # 或者插入到现有的日志表中，避免外键约束问题
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 使用 wipe_bomb_log 表来记录通用日志，因为它没有外键约束
            cursor.execute("""
                INSERT INTO wipe_bomb_log (user_id, contribution_amount, reward_multiplier, reward_amount, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, 0, 0.0, 0, datetime.now()))
            conn.commit()

    # --- Tax Log Methods ---
    def add_tax_record(self, record: TaxRecord) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1) 写入税收记录
            cursor.execute(
                """
                INSERT INTO taxes
                    (user_id, tax_amount, tax_rate, original_amount, balance_after, tax_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.user_id,
                    record.tax_amount,
                    record.tax_rate,
                    record.original_amount,
                    record.balance_after,
                    record.tax_type,
                    record.timestamp or datetime.now(self.UTC8),
                ),
            )

            # 2) 仅保留当前用户最近税收记录
            # 策略：优先保留每日资产税记录（重要），剩余空间保留最近的其他税收记录
            cutoff_time = datetime.now(self.UTC8) - timedelta(days=30)
            cursor.execute(
                """
                DELETE FROM taxes
                WHERE user_id = ?
                  AND tax_id NOT IN (
                    -- 保留所有30天内的每日资产税（核心记录，必须保留）
                    SELECT tax_id FROM taxes
                    WHERE user_id = ?
                      AND tax_type = '每日资产税'
                      AND timestamp >= ?
                    UNION
                    -- 保留最近50条其他税收记录
                    SELECT tax_id FROM (
                        SELECT tax_id, timestamp
                        FROM taxes
                        WHERE user_id = ?
                          AND tax_type != '每日资产税'
                        ORDER BY timestamp DESC, tax_id DESC
                        LIMIT 50
                    )
                  )
                """,
                (record.user_id, record.user_id, cutoff_time, record.user_id),
            )

            # 3) 清理30天前的税收记录（全局）
            cursor.execute(
                """
                DELETE FROM taxes
                WHERE timestamp < ?
                """,
                (cutoff_time,),
            )

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
    
    def has_daily_tax_today(self, reset_hour: int = 0) -> bool:
        """检查今天是否已经执行过每日资产税"""
        from ..utils import get_last_reset_time
        last_reset = get_last_reset_time(reset_hour)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM taxes
                WHERE tax_type = '每日资产税'
                AND timestamp >= ?
            """, (last_reset,))
            result = cursor.fetchone()
            return result[0] > 0 if result else False
    
    def has_user_daily_tax_today(self, user_id: str, reset_hour: int = 0) -> bool:
        """检查某个用户今天是否已经被征收过每日资产税"""
        from ..utils import get_last_reset_time
        last_reset = get_last_reset_time(reset_hour)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM taxes
                WHERE user_id = ?
                AND tax_type = '每日资产税'
                AND timestamp >= ?
            """, (user_id, last_reset))
            result = cursor.fetchone()
            return result[0] > 0 if result else False

    def get_max_wipe_bomb_multiplier(self, user_id: str) -> float:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(reward_multiplier) FROM wipe_bomb_log
                WHERE user_id = ?
            """, (user_id,))
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0.0

    def get_min_wipe_bomb_multiplier(self, user_id: str) -> Optional[float]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MIN(reward_multiplier) FROM wipe_bomb_log
                WHERE user_id = ?
            """, (user_id,))
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else None

    def get_gacha_records_count_today(
        self, user_id: str, gacha_pool_id: int
    ) -> int:
        # 获取 UTC+8 的今天的开始和结束时间点
        today_start_utc8 = datetime.now(self.UTC8).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end_utc8 = today_start_utc8 + timedelta(days=1)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM gacha_records
                WHERE user_id = ? AND gacha_pool_id = ? AND timestamp >= ? AND timestamp < ?
                """,
                (user_id, gacha_pool_id, today_start_utc8, today_end_utc8),
            )
            result = cursor.fetchone()
            return result[0] if result else 0

    # --- 用户鱼类统计（用于图鉴与个人纪录） ---
    def get_user_fish_stats(self, user_id: str) -> List[UserFishStat]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, fish_id, first_caught_at, last_caught_at,
                       max_weight, min_weight, total_caught, total_weight
                FROM user_fish_stats
                WHERE user_id = ?
                ORDER BY last_caught_at DESC
                """,
                (user_id,),
            )
            return [self._row_to_user_fish_stat(row) for row in cursor.fetchall()]

    def get_user_fish_stat(self, user_id: str, fish_id: int) -> Optional[UserFishStat]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, fish_id, first_caught_at, last_caught_at,
                       max_weight, min_weight, total_caught, total_weight
                FROM user_fish_stats
                WHERE user_id = ? AND fish_id = ?
                LIMIT 1
                """,
                (user_id, fish_id),
            )
            row = cursor.fetchone()
            return self._row_to_user_fish_stat(row) if row else None