import sqlite3
import threading
import time
from typing import Optional
from contextlib import contextmanager

from astrbot.api import logger


class DatabaseConnectionManager:
    """数据库连接管理器，提供线程安全的连接管理和重试机制"""
    
    def __init__(self, db_path: str, timeout: int = 30, max_retries: int = 3, retry_delay: float = 0.1):
        self.db_path = db_path
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._local = threading.local()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取一个线程安全的数据库连接"""
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = self._create_connection()
            self._local.connection = conn
        return conn
    
    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        conn = sqlite3.connect(
            self.db_path, 
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            timeout=self.timeout
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")  # 使用WAL模式提高并发性能
        conn.execute("PRAGMA synchronous = NORMAL;")  # 平衡性能和安全
        return conn
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器，支持重试机制"""
        conn = self._get_connection()
        try:
            yield conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                logger.warning(f"数据库锁定，操作无法在超时 ({self.timeout}s) 内完成: {e}")
            
            # 发生严重错误时，关闭并移除线程中的无效连接
            if conn:
                try:
                    conn.close()
                except:
                    pass
            if hasattr(self._local, "connection"):
                delattr(self._local, "connection")
            raise
        except Exception as e:
            logger.error(f"数据库操作发生未知错误: {e}")
            raise
    
    def close_connection(self):
        """关闭当前线程的数据库连接"""
        if hasattr(self._local, "connection"):
            try:
                self._local.connection.close()
            except:
                pass
            finally:
                delattr(self._local, "connection")
    
    def execute_with_retry(self, query: str, params: tuple = (), fetch: str = "none"):
        """执行SQL查询，支持重试机制
        
        Args:
            query: SQL查询语句
            params: 查询参数
            fetch: 获取结果的方式 ("none", "one", "all")
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch == "one":
                return cursor.fetchone()
            elif fetch == "all":
                return cursor.fetchall()
            else:
                conn.commit()
                return cursor.lastrowid if cursor.lastrowid else None
