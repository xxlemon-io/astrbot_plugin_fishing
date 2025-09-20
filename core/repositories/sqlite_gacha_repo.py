import sqlite3
import threading
from typing import Optional, List, Dict, Any

# 导入抽象基类和领域模型
from .abstract_repository import AbstractGachaRepository
from ..domain.models import GachaPool, GachaPoolItem

class SqliteGachaRepository(AbstractGachaRepository):
    """抽卡仓储的SQLite实现"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """获取一个线程安全的数据库连接。"""
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            # 开启外键约束，确保奖池删除时，其下的物品也被删除
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.connection = conn
        return conn

    # --- 私有映射辅助方法 ---
    def _row_to_gacha_pool(self, row: sqlite3.Row) -> Optional[GachaPool]:
        if not row:
            return None
        return GachaPool(**row)

    def _row_to_gacha_pool_item(self, row: sqlite3.Row) -> Optional[GachaPoolItem]:
        if not row:
            return None
        return GachaPoolItem(**row)

    # --- Gacha Read Methods ---
    def get_pool_by_id(self, pool_id: int) -> Optional[GachaPool]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM gacha_pools WHERE gacha_pool_id = ?", (pool_id,))
            pool_row = cursor.fetchone()
            if not pool_row:
                return None

            pool = self._row_to_gacha_pool(pool_row)
            pool.items = self.get_pool_items(pool_id) # 填充奖池物品
            return pool

    def get_pool_items(self, pool_id: int) -> List[GachaPoolItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 获取指定抽卡池的所有物品以及物品的详细信息
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    gacha_pool_item_id,
                    gacha_pool_id,
                    item_type,
                    item_id,
                    weight,
                    quantity
                FROM
                    gacha_pool_items
                WHERE
                    gacha_pool_id = ?
            """, (pool_id,))

            items = []
            for row in cursor.fetchall():
                item = GachaPoolItem(
                    gacha_pool_item_id=row[0],
                    gacha_pool_id=row[1],
                    item_type=row[2],
                    item_id=row[3],
                    weight=row[4],
                    quantity=row[5]
                )
                items.append(item)

            return items

    def get_all_pools(self) -> List[GachaPool]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM gacha_pools ORDER BY gacha_pool_id")
            rows = cursor.fetchall()  # 只获取一次结果

            pools = []
            for row in rows:
                pool = self._row_to_gacha_pool(row)
                if pool:
                    # 为每个奖池填充物品列表
                    pool.items = self.get_pool_items(pool.gacha_pool_id)
                    pools.append(pool)

            return pools

    def get_free_pools(self) -> List[GachaPool]:
        """查找所有免费的抽卡池"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM gacha_pools WHERE cost_coins = 0 AND cost_premium_currency = 0"
            )
            return [self._row_to_gacha_pool(row) for row in cursor.fetchall()]

    # --- Admin Panel CRUD Methods ---

    # Pool CRUD
    def add_pool_template(self, data: Dict[str, Any]) -> None:
        """后台添加一个新抽卡池"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO gacha_pools (name, description, cost_coins, cost_premium_currency, is_limited_time, open_until)
                VALUES (:name, :description, :cost_coins, :cost_premium_currency, :is_limited_time, :open_until)
            """, {
                "name": data.get("name"),
                "description": data.get("description"),
                "cost_coins": data.get("cost_coins", 0),
                "cost_premium_currency": data.get("cost_premium_currency", 0),
                "is_limited_time": 1 if data.get("is_limited_time") in (True, "1", 1, "on") else 0,
                "open_until": data.get("open_until")
            })
            conn.commit()

    def update_pool_template(self, pool_id: int, data: Dict[str, Any]) -> None:
        """后台更新一个抽卡池的信息"""
        data["gacha_pool_id"] = pool_id
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE gacha_pools SET
                    name = :name,
                    description = :description,
                    cost_coins = :cost_coins,
                    cost_premium_currency = :cost_premium_currency,
                    is_limited_time = :is_limited_time,
                    open_until = :open_until
                WHERE gacha_pool_id = :gacha_pool_id
            """, {
                "gacha_pool_id": pool_id,
                "name": data.get("name"),
                "description": data.get("description"),
                "cost_coins": data.get("cost_coins", 0),
                "cost_premium_currency": data.get("cost_premium_currency", 0),
                "is_limited_time": 1 if data.get("is_limited_time") in (True, "1", 1, "on") else 0,
                "open_until": data.get("open_until")
            })
            conn.commit()

    def delete_pool_template(self, pool_id: int) -> None:
        """后台删除一个抽卡池（其下的物品也会被级联删除）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM gacha_pools WHERE gacha_pool_id = ?", (pool_id,))
            conn.commit()

    def copy_pool_template(self, pool_id: int) -> int:
        """复制一个抽卡池及其所有物品，返回新的pool_id"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取原卡池信息
            cursor.execute("SELECT * FROM gacha_pools WHERE gacha_pool_id = ?", (pool_id,))
            original_pool = cursor.fetchone()
            if not original_pool:
                raise ValueError(f"Pool with ID {pool_id} not found")
            
            # 创建新卡池，名称加上"(副本)"
            cursor.execute("""
                INSERT INTO gacha_pools (name, description, cost_coins, cost_premium_currency, is_limited_time, open_until)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                f"{original_pool['name']} (副本)",
                original_pool['description'],
                original_pool['cost_coins'],
                original_pool['cost_premium_currency'],
                original_pool['is_limited_time'] if 'is_limited_time' in original_pool.keys() else 0,
                original_pool['open_until'] if 'open_until' in original_pool.keys() else None
            ))
            
            # 获取新卡池ID
            new_pool_id = cursor.lastrowid
            
            # 复制所有物品
            cursor.execute("SELECT * FROM gacha_pool_items WHERE gacha_pool_id = ?", (pool_id,))
            items = cursor.fetchall()
            
            for item in items:
                cursor.execute("""
                    INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, quantity, weight)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    new_pool_id,
                    item['item_type'],
                    item['item_id'],
                    item['quantity'],
                    item['weight']
                ))
            
            conn.commit()
            return new_pool_id

    # Pool Item CRUD
    def add_item_to_pool(self, pool_id: int, data: Dict[str, Any]) -> None:
        """后台向抽卡池添加一个物品"""
        item_full_id = data.get("item_full_id", "").split("-")
        if len(item_full_id) != 2:
            return
        item_type, item_id = item_full_id

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO gacha_pool_items (gacha_pool_id, item_type, item_id, quantity, weight)
                VALUES (?, ?, ?, ?, ?)
            """, (
                pool_id,
                item_type,
                item_id,
                data.get("quantity", 1),
                data.get("weight", 10)
            ))
            conn.commit()

    def update_pool_item(self, item_pool_id: int, data: Dict[str, Any]) -> None:
        """后台更新一个抽卡池物品的信息，支持部分更新"""
        if not data:
            return

        updates = []
        params = []

        # 处理 item_full_id
        if "item_full_id" in data and data["item_full_id"]:
            item_full_id = data["item_full_id"].split("-")
            if len(item_full_id) == 2:
                item_type, item_id = item_full_id
                updates.append("item_type = ?")
                updates.append("item_id = ?")
                params.extend([item_type, item_id])

        # 处理 quantity
        if "quantity" in data:
            updates.append("quantity = ?")
            params.append(data["quantity"])

        # 处理 weight
        if "weight" in data:
            updates.append("weight = ?")
            params.append(data["weight"])

        # 如果没有任何需要更新的字段，则直接返回
        if not updates:
            return

        params.append(item_pool_id)

        set_clause = ", ".join(updates)
        query = f"UPDATE gacha_pool_items SET {set_clause} WHERE gacha_pool_item_id = ?"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            conn.commit()

    def delete_pool_item(self, item_pool_id: int) -> None:
        """后台删除一个抽卡池物品"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM gacha_pool_items WHERE gacha_pool_item_id = ?", (item_pool_id,))
            conn.commit()
