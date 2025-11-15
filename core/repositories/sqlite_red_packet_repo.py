"""
红包数据仓储层
"""

import sqlite3
import threading
from datetime import datetime
from typing import Optional, List

from astrbot.api import logger

from ..domain.models import RedPacket, RedPacketRecord


class SqliteRedPacketRepository:
    """红包数据仓储的SQLite实现"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.connection = conn
        return conn

    def _parse_datetime(self, dt_val):
        """解析日期时间"""
        if isinstance(dt_val, datetime):
            return dt_val
        if isinstance(dt_val, str):
            try:
                return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
            except ValueError:
                try:
                    return datetime.strptime(dt_val, "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    try:
                        return datetime.strptime(dt_val, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        return None
        return None

    def _row_to_red_packet(self, row: sqlite3.Row) -> Optional[RedPacket]:
        """将数据库行转换为RedPacket对象"""
        if not row:
            return None
        
        return RedPacket(
            packet_id=row["packet_id"],
            sender_id=row["sender_id"],
            group_id=row["group_id"],
            packet_type=row["packet_type"],
            total_amount=row["total_amount"],
            total_count=row["total_count"],
            remaining_amount=row["remaining_amount"],
            remaining_count=row["remaining_count"],
            password=row["password"],
            created_at=self._parse_datetime(row["created_at"]),
            expires_at=self._parse_datetime(row["expires_at"]),
            is_expired=bool(row["is_expired"])
        )

    def _row_to_record(self, row: sqlite3.Row) -> Optional[RedPacketRecord]:
        """将数据库行转换为RedPacketRecord对象"""
        if not row:
            return None
        
        return RedPacketRecord(
            record_id=row["record_id"],
            packet_id=row["packet_id"],
            user_id=row["user_id"],
            amount=row["amount"],
            claimed_at=self._parse_datetime(row["claimed_at"])
        )

    def create_red_packet(self, packet: RedPacket) -> int:
        """创建红包"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO red_packets (
                    sender_id, group_id, packet_type, total_amount, total_count,
                    remaining_amount, remaining_count, password, created_at, expires_at, is_expired
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                packet.sender_id, packet.group_id, packet.packet_type,
                packet.total_amount, packet.total_count,
                packet.remaining_amount, packet.remaining_count,
                packet.password, packet.created_at, packet.expires_at, packet.is_expired
            ))
            conn.commit()
            return cursor.lastrowid

    def get_red_packet_by_id(self, packet_id: int) -> Optional[RedPacket]:
        """根据ID获取红包"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM red_packets WHERE packet_id = ?", (packet_id,))
            row = cursor.fetchone()
            return self._row_to_red_packet(row)

    def get_active_red_packets_in_group(self, group_id: str) -> List[RedPacket]:
        """获取群组中的活跃红包"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM red_packets 
                WHERE group_id = ? AND is_expired = 0 AND remaining_count > 0
                ORDER BY created_at DESC
            """, (group_id,))
            return [self._row_to_red_packet(row) for row in cursor.fetchall()]

    def update_red_packet(self, packet: RedPacket) -> None:
        """更新红包信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE red_packets SET
                    remaining_amount = ?,
                    remaining_count = ?,
                    is_expired = ?
                WHERE packet_id = ?
            """, (
                packet.remaining_amount,
                packet.remaining_count,
                packet.is_expired,
                packet.packet_id
            ))
            conn.commit()

    def create_claim_record(self, record: RedPacketRecord) -> int:
        """创建领取记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO red_packet_records (packet_id, user_id, amount, claimed_at)
                VALUES (?, ?, ?, ?)
            """, (record.packet_id, record.user_id, record.amount, record.claimed_at))
            conn.commit()
            return cursor.lastrowid

    def has_user_claimed(self, packet_id: int, user_id: str) -> bool:
        """检查用户是否已领取"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM red_packet_records 
                WHERE packet_id = ? AND user_id = ?
            """, (packet_id, user_id))
            count = cursor.fetchone()[0]
            return count > 0

    def get_claim_records_by_packet(self, packet_id: int) -> List[RedPacketRecord]:
        """获取红包的所有领取记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM red_packet_records 
                WHERE packet_id = ?
                ORDER BY claimed_at ASC
            """, (packet_id,))
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def expire_old_packets(self, current_time: datetime) -> int:
        """过期旧红包"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE red_packets 
                SET is_expired = 1 
                WHERE expires_at < ? AND is_expired = 0
            """, (current_time,))
            conn.commit()
            return cursor.rowcount

    def clean_old_red_packets(self, days_to_keep: int = 7) -> int:
        """
        清理过期的红包记录（保留最近N天）
        
        Args:
            days_to_keep: 保留最近多少天的记录，默认7天
        
        Returns:
            删除的红包数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 计算截止时间
            from datetime import timedelta
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            
            # 先获取要删除的红包ID列表
            cursor.execute("""
                SELECT packet_id FROM red_packets 
                WHERE is_expired = 1 AND expires_at < ?
            """, (cutoff_time,))
            packet_ids = [row[0] for row in cursor.fetchall()]
            
            if not packet_ids:
                return 0
            
            # 删除这些红包的领取记录
            placeholders = ','.join('?' * len(packet_ids))
            cursor.execute(f"""
                DELETE FROM red_packet_records 
                WHERE packet_id IN ({placeholders})
            """, packet_ids)
            
            # 删除红包本身
            cursor.execute(f"""
                DELETE FROM red_packets 
                WHERE packet_id IN ({placeholders})
            """, packet_ids)
            
            # 检查是否还有红包记录
            cursor.execute("SELECT COUNT(*) FROM red_packets")
            remaining_count = cursor.fetchone()[0]
            
            # 如果没有红包记录了，重置自增ID
            if remaining_count == 0:
                cursor.execute("""
                    DELETE FROM sqlite_sequence WHERE name = 'red_packets'
                """)
                logger.info("已重置红包ID计数器")
            
            conn.commit()
            deleted_count = len(packet_ids)
            
            logger.info(f"清理了 {deleted_count} 个过期红包记录（{days_to_keep}天前）")
            return deleted_count

    def get_group_red_packets(self, group_id: str) -> List[RedPacket]:
        """获取指定群组的所有红包（包括已过期的）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM red_packets 
                WHERE group_id = ?
                ORDER BY created_at DESC
            """, (group_id,))
            return [self._row_to_red_packet(row) for row in cursor.fetchall()]

    def revoke_group_red_packets(self, group_id: str) -> tuple[int, int, list]:
        """
        撤回指定群组的所有未领完红包，并返回退款信息
        
        Returns:
            (退还的红包数量, 退还的总金额, 红包详情列表)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取该群所有未领完的红包
            cursor.execute("""
                SELECT packet_id, sender_id, remaining_amount 
                FROM red_packets 
                WHERE group_id = ? AND is_expired = 0 AND remaining_amount > 0
            """, (group_id,))
            
            packets_to_revoke = cursor.fetchall()
            
            if not packets_to_revoke:
                return (0, 0, [])
            
            # 标记这些红包为已过期
            packet_ids = [p[0] for p in packets_to_revoke]
            placeholders = ','.join('?' * len(packet_ids))
            cursor.execute(f"""
                UPDATE red_packets 
                SET is_expired = 1, remaining_count = 0, remaining_amount = 0
                WHERE packet_id IN ({placeholders})
            """, packet_ids)
            
            conn.commit()
            
            # 计算退还信息
            refund_count = len(packets_to_revoke)
            refund_amount = sum(p[2] for p in packets_to_revoke)
            
            return (refund_count, refund_amount, packets_to_revoke)

    def revoke_all_red_packets(self) -> tuple[int, int, list]:
        """
        撤回所有未领完的红包，并返回退款信息
        
        Returns:
            (退还的红包数量, 退还的总金额, 红包详情列表)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取所有未领完的红包
            cursor.execute("""
                SELECT packet_id, sender_id, remaining_amount 
                FROM red_packets 
                WHERE is_expired = 0 AND remaining_amount > 0
            """)
            
            packets_to_revoke = cursor.fetchall()
            
            if not packets_to_revoke:
                return (0, 0, [])
            
            # 标记所有红包为已过期
            cursor.execute("""
                UPDATE red_packets 
                SET is_expired = 1, remaining_count = 0, remaining_amount = 0
                WHERE is_expired = 0 AND remaining_amount > 0
            """)
            
            conn.commit()
            
            # 计算退还信息
            refund_count = len(packets_to_revoke)
            refund_amount = sum(p[2] for p in packets_to_revoke)
            
            return (refund_count, refund_amount, packets_to_revoke)

    def delete_group_red_packets(self, group_id: str) -> int:
        """
        删除指定群组的所有红包记录
        
        Returns:
            删除的红包数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取该群所有红包ID
            cursor.execute("""
                SELECT packet_id FROM red_packets WHERE group_id = ?
            """, (group_id,))
            packet_ids = [row[0] for row in cursor.fetchall()]
            
            if not packet_ids:
                return 0
            
            # 删除领取记录
            placeholders = ','.join('?' * len(packet_ids))
            cursor.execute(f"""
                DELETE FROM red_packet_records 
                WHERE packet_id IN ({placeholders})
            """, packet_ids)
            
            # 删除红包
            cursor.execute("""
                DELETE FROM red_packets WHERE group_id = ?
            """, (group_id,))
            
            # 检查是否还有红包记录
            cursor.execute("SELECT COUNT(*) FROM red_packets")
            remaining_count = cursor.fetchone()[0]
            
            # 如果没有红包记录了，重置自增ID
            if remaining_count == 0:
                cursor.execute("""
                    DELETE FROM sqlite_sequence WHERE name = 'red_packets'
                """)
                logger.info("已重置红包ID计数器")
            
            conn.commit()
            
            return len(packet_ids)

    def delete_all_red_packets(self) -> int:
        """
        删除所有红包记录并重置ID计数器
        
        Returns:
            删除的红包数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取红包总数
            cursor.execute("SELECT COUNT(*) FROM red_packets")
            count = cursor.fetchone()[0]
            
            # 删除所有领取记录
            cursor.execute("DELETE FROM red_packet_records")
            
            # 删除所有红包
            cursor.execute("DELETE FROM red_packets")
            
            # 重置自增ID计数器
            cursor.execute("""
                DELETE FROM sqlite_sequence WHERE name = 'red_packets'
            """)
            
            conn.commit()
            
            logger.info(f"已删除 {count} 个红包记录并重置红包ID计数器")
            
            return count

    def cleanup_expired_red_packets(self) -> int:
        """
        清理所有过期红包（已过期24小时以上的）
        
        Returns:
            清理的红包数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 查找过期红包（已过期24小时以上）
            from datetime import datetime, timedelta
            expired_time = datetime.now() - timedelta(hours=24)
            
            cursor.execute("""
                SELECT id FROM red_packets
                WHERE expired_at < ? AND status IN ('active', 'expired')
            """, (expired_time,))
            
            expired_packets = cursor.fetchall()
            
            if not expired_packets:
                return 0
            
            # 删除过期红包及其领取记录
            packet_ids = [p[0] for p in expired_packets]
            placeholders = ','.join(['?'] * len(packet_ids))
            
            cursor.execute(f"""
                DELETE FROM red_packet_records WHERE red_packet_id IN ({placeholders})
            """, packet_ids)
            
            cursor.execute(f"""
                DELETE FROM red_packets WHERE id IN ({placeholders})
            """, packet_ids)
            
            conn.commit()
            
            logger.info(f"已清理 {len(packet_ids)} 个过期红包")
            
            return len(packet_ids)
