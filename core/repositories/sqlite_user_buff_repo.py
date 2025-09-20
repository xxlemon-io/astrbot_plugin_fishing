import sqlite3
import json
from typing import List, Optional
from datetime import datetime

from ..domain.models import UserBuff
from .abstract_repository import AbstractUserBuffRepository
from ...utils import get_db_path, DATETIME_FORMAT


class SqliteUserBuffRepository(AbstractUserBuffRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _to_domain(self, row: sqlite3.Row) -> UserBuff:
        return UserBuff(
            id=row[0],
            user_id=row[1],
            buff_type=row[2],
            payload=row[3],
            started_at=datetime.strptime(row[4], DATETIME_FORMAT),
            expires_at=(
                datetime.strptime(row[5], DATETIME_FORMAT) if row[5] else None
            ),
        )

    def add(self, buff: UserBuff):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_buffs (user_id, buff_type, payload, started_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    buff.user_id,
                    buff.buff_type,
                    buff.payload,
                    buff.started_at.strftime(DATETIME_FORMAT),
                    buff.expires_at.strftime(DATETIME_FORMAT) if buff.expires_at else None,
                ),
            )
            conn.commit()

    def get_active_by_user_and_type(
        self, user_id: str, buff_type: str
    ) -> Optional[UserBuff]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, buff_type, payload, started_at, expires_at
                FROM user_buffs
                WHERE user_id = ? AND buff_type = ? AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY expires_at DESC
                LIMIT 1
                """,
                (user_id, buff_type, datetime.now().strftime(DATETIME_FORMAT)),
            )
            row = cursor.fetchone()
            return self._to_domain(row) if row else None

    def get_all_active_by_user(self, user_id: str) -> List[UserBuff]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, buff_type, payload, started_at, expires_at
                FROM user_buffs
                WHERE user_id = ? AND (expires_at IS NULL OR expires_at > ?)
                """,
                (user_id, datetime.now().strftime(DATETIME_FORMAT)),
            )
            rows = cursor.fetchall()
            return [self._to_domain(row) for row in rows]

    def delete_expired(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM user_buffs WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (datetime.now().strftime(DATETIME_FORMAT),),
            )
            conn.commit()

    def delete(self, buff_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_buffs WHERE id = ?", (buff_id,))
            conn.commit()
