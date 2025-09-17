import sqlite3
import threading
import logging
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
            conn = sqlite3.connect(
                self.db_path, 
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.connection = conn
        return conn

    def _row_to_market_listing(self, row: sqlite3.Row) -> Optional[MarketListing]:
        """将数据库行对象映射到 MarketListing 领域模型。"""
        if not row:
            return None
        
        # 转换为字典并处理日期字段
        data = dict(row)
        
        # 确保 listed_at 是 datetime 对象
        if 'listed_at' in data and isinstance(data['listed_at'], str):
            try:
                data['listed_at'] = datetime.fromisoformat(data['listed_at'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # 如果解析失败，记录警告并使用当前时间
                logging.warning(f"Failed to parse listed_at: {data['listed_at']}. Falling back to current time.")
                data['listed_at'] = datetime.now()
        
        return MarketListing(**data)


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

    def get_all_listings(self, page: int = None, per_page: int = None, 
                        item_type: str = None, min_price: int = None, 
                        max_price: int = None, search: str = None) -> tuple:
        """
        获取市场商品，支持筛选和分页。
        返回 (listings, total_count) 元组。
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 构建WHERE条件
            where_conditions = []
            params = []
            
            if item_type:
                where_conditions.append("m.item_type = ?")
                params.append(item_type)
                
            if min_price is not None:
                where_conditions.append("m.price >= ?")
                params.append(min_price)
                
            if max_price is not None:
                where_conditions.append("m.price <= ?")
                params.append(max_price)
                
            if search:
                # 搜索商品名称和卖家昵称
                search_condition = """(
                    (m.item_type = 'rod' AND r.name LIKE ?) OR
                    (m.item_type = 'accessory' AND a.name LIKE ?) OR
                    u.nickname LIKE ?
                )"""
                where_conditions.append(search_condition)
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            # 首先获取总数
            count_query = f"""
                SELECT COUNT(*)
                FROM market m
                JOIN users u ON m.user_id = u.user_id
                LEFT JOIN rods r ON m.item_type = 'rod' AND m.item_id = r.rod_id
                LEFT JOIN accessories a ON m.item_type = 'accessory' AND m.item_id = a.accessory_id
                WHERE {where_clause}
            """
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]
            
            # 构建主查询
            query = f"""
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
                WHERE {where_clause}
                ORDER BY m.listed_at DESC
            """
            
            # 添加分页
            if page is not None and per_page is not None:
                offset = (page - 1) * per_page
                query += " LIMIT ? OFFSET ?"
                params.extend([per_page, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            listings = [self._row_to_market_listing(row) for row in rows]
            
            return listings, total_count

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