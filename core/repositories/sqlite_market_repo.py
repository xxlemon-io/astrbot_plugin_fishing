import sqlite3
import threading
from typing import Optional, List
from datetime import datetime

# 导入抽象基类和领域模型
from .abstract_repository import AbstractMarketRepository
from ..domain.models import MarketListing

class SqliteMarketRepository(AbstractMarketRepository):
    """市场仓储的SQLite实现"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """获取一个线程安全的数据库连接。"""
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.connection = conn
        return conn

    def _row_to_market_listing(self, row: sqlite3.Row) -> Optional[MarketListing]:
        """将数据库行对象映射到 MarketListing 领域模型。"""
        if not row:
            return None
        return MarketListing(**row)


    def get_listing_by_id(self, market_id: int) -> Optional[MarketListing]:
        """获取单个市场商品"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            #  采用连表查询补全其他字段
            # cursor.execute("SELECT * FROM market WHERE market_id = ?", (market_id,))
            cursor.execute("""
                SELECT
                    m.market_id,
                    m.user_id,
                    u.nickname AS seller_nickname,
                    m.item_type,
                    m.item_id,
                    m.quantity,
                    m.price,
                    m.refine_level,
                    m.listed_at,
                    CASE
                        WHEN m.item_type = 'rod' THEN r.name
                        WHEN m.item_type = 'accessory' THEN a.name
                        ELSE '未知物品'
                        END AS item_name,
                        CASE
                        WHEN m.item_type = 'rod' THEN r.description
                        WHEN m.item_type = 'accessory' THEN a.description
                        ELSE ''
                        END AS item_description
                        FROM market m
                    JOIN users u ON m.user_id = u.user_id
                    LEFT JOIN rods r ON m.item_type = 'rod' AND m.item_id = r.rod_id
                    LEFT JOIN accessories a ON m.item_type = 'accessory' AND m.item_id = a.accessory_id
                    WHERE m.market_id = ?
            """, (market_id,))

            row = cursor.fetchone()
            return self._row_to_market_listing(row)

    def get_all_listings(self) -> List[MarketListing]:
        """
        获取所有市场商品，并连接（JOIN）其他表以获取商品名称和卖家昵称。
        注意：此方法返回的是一个字典列表（DTO），而非纯粹的领域模型列表，
        因为它包含了来自多个表的聚合信息，便于在表现层直接展示。
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 一个查询处理所有类型的物品
            query = """
                SELECT
                    m.market_id,
                    m.user_id,
                    u.nickname AS seller_nickname,
                    m.item_type,
                    m.item_id,
                    m.quantity,
                    m.price,
                    m.refine_level,
                    m.listed_at,
                    CASE
                        WHEN m.item_type = 'rod' THEN r.name
                        WHEN m.item_type = 'accessory' THEN a.name
                        ELSE '未知物品'
                    END AS item_name,
                    CASE
                        WHEN m.item_type = 'rod' THEN r.description
                        WHEN m.item_type = 'accessory' THEN a.description
                        ELSE ''
                    END AS item_description
                FROM market m
                JOIN users u ON m.user_id = u.user_id
                LEFT JOIN rods r ON m.item_type = 'rod' AND m.item_id = r.rod_id
                LEFT JOIN accessories a ON m.item_type = 'accessory' AND m.item_id = a.accessory_id
                ORDER BY m.listed_at DESC;
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            return [self._row_to_market_listing(row) for row in rows]

    def add_listing(self, listing: MarketListing) -> None:
        """添加一个市场商品"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO market (user_id, item_type, item_id, quantity, price, listed_at, refine_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                listing.user_id,
                listing.item_type,
                listing.item_id,
                listing.quantity,
                listing.price,
                listing.listed_at or datetime.now(),
                listing.refine_level
            ))
            conn.commit()

    def remove_listing(self, market_id: int) -> None:
        """移除一个市场商品（通常在购买成功或下架后调用）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM market WHERE market_id = ?", (market_id,))
            conn.commit()

    def update_listing(self, listing: MarketListing) -> None:
        """更新市场商品信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE market 
                SET price = ?, refine_level = ?
                WHERE market_id = ?
            """, (
                listing.price,
                listing.refine_level,
                listing.market_id
            ))
            conn.commit()