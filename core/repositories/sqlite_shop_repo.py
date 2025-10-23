import sqlite3
import threading
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .abstract_repository import AbstractShopRepository


class SqliteShopRepository(AbstractShopRepository):
    """商店系统的 SQLite 实现（新设计：shops + shop_items + shop_item_costs + shop_item_rewards）"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.connection = conn
        return conn

    def _normalize_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """标准化行数据，处理类型转换"""
        if not row:
            return {}
        data = dict(row)
        # 布尔值转换
        for k in ("is_active",):
            if k in data and isinstance(data[k], int):
                data[k] = bool(data[k])
        # 时间解析（datetime类型）
        for k in ("created_at", "updated_at", "timestamp"):
            if k in data and data[k] and isinstance(data[k], str):
                try:
                    data[k] = datetime.fromisoformat(data[k].replace("Z", "+00:00"))
                except Exception:
                    pass
        
        # 时间字段保持字符串格式（用于前端表单）
        for k in ("start_time", "end_time"):
            if k in data and data[k]:
                if isinstance(data[k], str):
                    # 确保格式正确
                    data[k] = data[k]
                elif hasattr(data[k], 'strftime'):
                    # 如果是datetime对象，转换为字符串
                    data[k] = data[k].strftime('%Y-%m-%d %H:%M:%S')
        # 时间格式处理（TIME类型，保持字符串格式）
        for k in ("daily_start_time", "daily_end_time"):
            if k in data and data[k]:
                # 确保时间格式为 HH:MM
                if isinstance(data[k], str) and ':' in data[k]:
                    # 如果包含秒数，去掉秒数部分
                    if data[k].count(':') == 2:
                        data[k] = data[k][:5]  # 只保留 HH:MM
                elif hasattr(data[k], 'strftime'):
                    # 如果是时间对象，转换为字符串
                    data[k] = data[k].strftime('%H:%M')
        return data

    # ---- 商店管理（Shops） ----
    def get_active_shops(self, shop_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取活跃的商店列表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        where = ["is_active = 1"]
        params: List[Any] = []
        
        # 时间检查
        now = datetime.now().isoformat(sep=" ")
        where.append("(start_time IS NULL OR start_time <= ?)")
        where.append("(end_time IS NULL OR end_time >= ?)")
        params.extend([now, now])
        
        # 每日时段检查 - 处理跨日情况
        current_time = datetime.now().time().strftime("%H:%M")
        # 对于跨日营业时间（如21:00-04:00），需要特殊处理
        where.append("(daily_start_time IS NULL OR daily_end_time IS NULL OR (daily_start_time <= daily_end_time AND daily_start_time <= ? AND daily_end_time >= ?) OR (daily_start_time > daily_end_time AND (daily_start_time <= ? OR daily_end_time >= ?)))")
        params.extend([current_time, current_time, current_time, current_time])
        
        if shop_type:
            where.append("shop_type = ?")
            params.append(shop_type)
            
        sql = f"SELECT * FROM shops WHERE {' AND '.join(where)} ORDER BY sort_order ASC, shop_id ASC"
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [self._normalize_row(r) for r in rows]

    def get_all_shops(self) -> List[Dict[str, Any]]:
        """获取所有商店列表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shops ORDER BY sort_order ASC, shop_id ASC")
        rows = cursor.fetchall()
        return [self._normalize_row(r) for r in rows]

    def get_shop_by_id(self, shop_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取商店信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shops WHERE shop_id = ?", (shop_id,))
        row = cursor.fetchone()
        return self._normalize_row(row) if row else None

    def create_shop(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新商店"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO shops (
                name, description, shop_type, is_active, 
                start_time, end_time, daily_start_time, daily_end_time, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data.get("description"),
                data.get("shop_type", "normal"),
                1 if data.get("is_active", True) else 0,
                data.get("start_time"),
                data.get("end_time"),
                data.get("daily_start_time"),
                data.get("daily_end_time"),
                data.get("sort_order", 100),
            ),
        )
        conn.commit()
        return self.get_shop_by_id(cursor.lastrowid)  # type: ignore

    def update_shop(self, shop_id: int, data: Dict[str, Any]) -> None:
        """更新商店信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        fields = []
        params: List[Any] = []
        
        for k in [
            "name", "description", "shop_type", "is_active",
            "start_time", "end_time", "daily_start_time", "daily_end_time", "sort_order"
        ]:
            if k in data:
                fields.append(f"{k} = ?")
                v = data[k]
                if k == "is_active":
                    v = 1 if v else 0
                params.append(v)
                
        if not fields:
            return
            
        params.append(shop_id)
        cursor.execute(
            f"UPDATE shops SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?",
            params
        )
        conn.commit()

    def delete_shop(self, shop_id: int) -> None:
        """删除商店"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shops WHERE shop_id = ?", (shop_id,))
        conn.commit()

    # ---- 商店商品管理（Shop Items） ----
    def get_shop_items(self, shop_id: int) -> List[Dict[str, Any]]:
        """获取商店的所有商品"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM shop_items 
            WHERE shop_id = ? 
            ORDER BY sort_order ASC, item_id ASC
            """,
            (shop_id,)
        )
        rows = cursor.fetchall()
        return [self._normalize_row(r) for r in rows]

    def get_shop_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取商店商品"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shop_items WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        return self._normalize_row(row) if row else None

    def create_shop_item(self, shop_id: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建商店商品"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO shop_items (
                shop_id, name, description, category,
                stock_total, stock_sold, per_user_limit, per_user_daily_limit,
                is_active, start_time, end_time, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shop_id,
                item_data["name"],
                item_data.get("description"),
                item_data.get("category", "general"),
                item_data.get("stock_total"),
                item_data.get("stock_sold", 0),
                item_data.get("per_user_limit"),
                item_data.get("per_user_daily_limit"),
                1 if item_data.get("is_active", True) else 0,
                item_data.get("start_time"),
                item_data.get("end_time"),
                item_data.get("sort_order", 100),
            ),
        )
        conn.commit()
        return self.get_shop_item_by_id(cursor.lastrowid)  # type: ignore

    def update_shop_item(self, item_id: int, data: Dict[str, Any]) -> None:
        """更新商店商品"""
        conn = self._get_connection()
        cursor = conn.cursor()
        fields = []
        params: List[Any] = []
        
        for k in [
            "name", "description", "category", "is_active",
            "start_time", "end_time", "stock_total", "stock_sold",
            "per_user_limit", "per_user_daily_limit", "sort_order"
        ]:
            if k in data:
                fields.append(f"{k} = ?")
                v = data[k]
                if k == "is_active":
                    v = 1 if v else 0
                params.append(v)
                
        if not fields:
            return
            
        params.append(item_id)
        cursor.execute(
            f"UPDATE shop_items SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE item_id = ?",
            params
        )
        conn.commit()

    def delete_shop_item(self, item_id: int) -> None:
        """删除商店商品"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shop_items WHERE item_id = ?", (item_id,))
        conn.commit()

    def increase_item_sold(self, item_id: int, delta: int) -> None:
        """增加商品销量"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE shop_items SET stock_sold = COALESCE(stock_sold, 0) + ?, updated_at = CURRENT_TIMESTAMP WHERE item_id = ?",
            (delta, item_id)
        )
        conn.commit()

    # ---- 商品成本管理（Shop Item Costs） ----
    def get_item_costs(self, item_id: int) -> List[Dict[str, Any]]:
        """获取商品的所有成本"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT *, quality_level FROM shop_item_costs WHERE item_id = ? ORDER BY group_id ASC, cost_id ASC",
            (item_id,)
        )
        rows = cursor.fetchall()
        return [self._normalize_row(r) for r in rows]

    def add_item_cost(self, item_id: int, cost_data: Dict[str, Any]) -> None:
        """添加商品成本"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO shop_item_costs (
                item_id, cost_type, cost_amount, cost_item_id,
                cost_relation, group_id, quality_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                cost_data["cost_type"],
                cost_data["cost_amount"],
                cost_data.get("cost_item_id"),
                cost_data.get("cost_relation", "and"),
                cost_data.get("group_id"),
                cost_data.get("quality_level", 0),
            ),
        )
        conn.commit()

    def update_item_cost(self, cost_id: int, data: Dict[str, Any]) -> None:
        """更新商品成本"""
        conn = self._get_connection()
        cursor = conn.cursor()
        fields = []
        params: List[Any] = []
        
        for k in ["cost_type", "cost_amount", "cost_item_id", "cost_relation", "group_id", "quality_level"]:
            if k in data:
                fields.append(f"{k} = ?")
                params.append(data[k])
                
        if not fields:
            return
            
        params.append(cost_id)
        cursor.execute(
            f"UPDATE shop_item_costs SET {', '.join(fields)} WHERE cost_id = ?",
            params
        )
        conn.commit()

    def delete_item_cost(self, cost_id: int) -> None:
        """删除商品成本"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shop_item_costs WHERE cost_id = ?", (cost_id,))
        conn.commit()

    # ---- 商品奖励管理（Shop Item Rewards） ----
    def get_item_rewards(self, item_id: int) -> List[Dict[str, Any]]:
        """获取商品的所有奖励"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT *, quality_level FROM shop_item_rewards WHERE item_id = ? ORDER BY reward_id ASC",
            (item_id,)
        )
        rows = cursor.fetchall()
        return [self._normalize_row(r) for r in rows]

    def add_item_reward(self, item_id: int, reward_data: Dict[str, Any]) -> None:
        """添加商品奖励"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO shop_item_rewards (
                item_id, reward_type, reward_item_id, reward_quantity, reward_refine_level, quality_level
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                reward_data["reward_type"],
                reward_data.get("reward_item_id"),
                reward_data.get("reward_quantity", 1),
                reward_data.get("reward_refine_level"),
                reward_data.get("quality_level", 0),
            ),
        )
        conn.commit()

    def update_item_reward(self, reward_id: int, data: Dict[str, Any]) -> None:
        """更新商品奖励"""
        conn = self._get_connection()
        cursor = conn.cursor()
        fields = []
        params: List[Any] = []
        
        for k in ["reward_type", "reward_item_id", "reward_quantity", "reward_refine_level", "quality_level"]:
            if k in data:
                fields.append(f"{k} = ?")
                params.append(data[k])
                
        if not fields:
            return
            
        params.append(reward_id)
        cursor.execute(
            f"UPDATE shop_item_rewards SET {', '.join(fields)} WHERE reward_id = ?",
            params
        )
        conn.commit()

    def delete_item_reward(self, reward_id: int) -> None:
        """删除商品奖励"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shop_item_rewards WHERE reward_id = ?", (reward_id,))
        conn.commit()

    # ---- 购买记录管理（Shop Purchase Records） ----
    def add_purchase_record(self, user_id: str, item_id: int, quantity: int) -> None:
        """记录购买"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO shop_purchase_records (user_id, item_id, quantity) VALUES (?, ?, ?)",
            (user_id, item_id, quantity)
        )
        conn.commit()

    def get_user_purchased_count(self, user_id: str, item_id: int, since: Optional[datetime] = None) -> int:
        """获取用户购买数量（用于限购检查）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if since is None:
            cursor.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM shop_purchase_records WHERE user_id = ? AND item_id = ?",
                (user_id, item_id)
            )
        else:
            cursor.execute(
                """
                SELECT COALESCE(SUM(quantity), 0)
                FROM shop_purchase_records
                WHERE user_id = ? AND item_id = ? AND timestamp >= ?
                """,
                (user_id, item_id, since.isoformat(sep=" "))
            )
        row = cursor.fetchone()
        return int(row[0] if row and row[0] is not None else 0)

    def get_user_purchase_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户购买历史"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT spr.*, si.name as item_name, s.name as shop_name
            FROM shop_purchase_records spr
            JOIN shop_items si ON spr.item_id = si.item_id
            JOIN shops s ON si.shop_id = s.shop_id
            WHERE spr.user_id = ?
            ORDER BY spr.timestamp DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        rows = cursor.fetchall()
        return [self._normalize_row(r) for r in rows]

    # ---- 兼容性方法（向后兼容） ----
    def get_active_offers(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取活跃商品（兼容旧接口）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        where = ["si.is_active = 1"]
        params: List[Any] = []
        
        # 时间检查
        now = datetime.now().isoformat(sep=" ")
        where.append("(si.start_time IS NULL OR si.start_time <= ?)")
        where.append("(si.end_time IS NULL OR si.end_time >= ?)")
        params.extend([now, now])
        
        if category:
            where.append("si.category = ?")
            params.append(category)
            
        sql = f"""
        SELECT si.*, s.name as shop_name, s.shop_type
        FROM shop_items si
        JOIN shops s ON si.shop_id = s.shop_id
        WHERE {' AND '.join(where)}
        ORDER BY si.sort_order ASC, si.item_id ASC
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [self._normalize_row(r) for r in rows]

    def get_offer_by_id(self, offer_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取商品（兼容旧接口）"""
        return self.get_shop_item_by_id(offer_id)