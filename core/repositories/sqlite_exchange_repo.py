from datetime import datetime
from typing import List, Optional

from ..domain.models import Commodity, Exchange, UserCommodity
from .abstract_repository import AbstractExchangeRepository
from ..database.connection_manager import DatabaseConnectionManager


class SQLiteExchangeRepository(AbstractExchangeRepository):
    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db_manager = db_manager

    def get_all_commodities(self) -> List[Commodity]:
        with self.db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT commodity_id, name, description FROM commodities")
            rows = c.fetchall()
            return [Commodity(*row) for row in rows]

    def get_commodity_by_id(self, commodity_id: str) -> Optional[Commodity]:
        with self.db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT commodity_id, name, description FROM commodities WHERE commodity_id=?", (commodity_id,))
            row = c.fetchone()
            return Commodity(*row) if row else None

    def get_prices_for_date(self, date: str) -> List[Exchange]:
        with self.db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT date, commodity_id, price FROM exchange_prices WHERE date=?", (date,))
            rows = c.fetchall()
            return [Exchange(*row) for row in rows]

    def add_exchange_price(self, price: Exchange) -> None:
        with self.db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO exchange_prices (date, commodity_id, price) VALUES (?, ?, ?)",
                      (price.date, price.commodity_id, price.price))
            conn.commit()

    def get_user_commodities(self, user_id: str) -> List[UserCommodity]:
        with self.db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT instance_id, user_id, commodity_id, quantity, purchase_price, purchased_at, expires_at
                FROM user_commodities WHERE user_id=?
            """, (user_id,))
            rows = c.fetchall()
            return [
                UserCommodity(
                    instance_id=row[0], user_id=row[1], commodity_id=row[2], quantity=row[3],
                    purchase_price=row[4], purchased_at=datetime.fromisoformat(row[5]),
                    expires_at=datetime.fromisoformat(row[6])
                ) for row in rows
            ]

    def add_user_commodity(self, user_commodity: UserCommodity) -> UserCommodity:
        with self.db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO user_commodities (user_id, commodity_id, quantity, purchase_price, purchased_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_commodity.user_id, user_commodity.commodity_id, user_commodity.quantity,
                user_commodity.purchase_price, user_commodity.purchased_at.isoformat(),
                user_commodity.expires_at.isoformat()
            ))
            user_commodity.instance_id = c.lastrowid
            conn.commit()
            return user_commodity

    def update_user_commodity_quantity(self, instance_id: int, new_quantity: int) -> None:
        with self.db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE user_commodities SET quantity=? WHERE instance_id=?", (new_quantity, instance_id))
            conn.commit()

    def delete_user_commodity(self, instance_id: int) -> None:
        with self.db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM user_commodities WHERE instance_id=?", (instance_id,))
            conn.commit()

    def get_user_commodity_by_instance_id(self, instance_id: int) -> Optional[UserCommodity]:
        with self.db_manager.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                            SELECT instance_id, user_id, commodity_id, quantity, purchase_price, purchased_at, expires_at
                            FROM user_commodities WHERE instance_id=?
                        """, (instance_id,))
            row = c.fetchone()
            if row:
                return UserCommodity(
                    instance_id=row[0], user_id=row[1], commodity_id=row[2], quantity=row[3],
                    purchase_price=row[4], purchased_at=datetime.fromisoformat(row[5]),
                    expires_at=datetime.fromisoformat(row[6])
                )
            return None
