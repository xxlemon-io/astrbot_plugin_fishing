import sqlite3
import os
import re
import importlib

from astrbot.api import logger


def get_current_version(cursor: sqlite3.Cursor) -> int:
    """获取当前数据库的版本号。"""
    try:
        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.OperationalError:
        return 0


def set_version(cursor: sqlite3.Cursor, version: int):
    """设置数据库的版本号。"""
    cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


def run_migrations(db_path: str, migrations_dir: str):
    """
    运行所有待处理的数据库迁移脚本。
    """
    logger.debug("开始执行数据库迁移...")
    # 确保版本表存在
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL PRIMARY KEY
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (0)")
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        current_version = get_current_version(cursor)
        logger.info(f"当前数据库版本: {current_version}")

    # 查找所有迁移脚本
    try:
        migration_files = sorted(
            [f for f in os.listdir(migrations_dir) if f.endswith('.py') and re.match(r'^\d{3}_', f)],
            key=lambda f: int(f.split('_')[0])
        )
        logger.debug(f"找到 {len(migration_files)} 个迁移脚本: {migration_files}")
    except FileNotFoundError:
        logger.debug(f"迁移目录 '{migrations_dir}' 不存在，跳过迁移。")
        return

    for filename in migration_files:
        version = int(filename.split('_')[0])
        if version > current_version:
            logger.debug(f"正在应用迁移脚本: {filename}...")
            try:
                module_name = f"data.plugins.astrbot_plugin_fishing.core.database.migrations.{filename[:-3]}"
                migration_module = importlib.import_module(module_name)

                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    # 每个迁移脚本都在一个事务中执行
                    try:
                        cursor.execute("BEGIN TRANSACTION")
                        # 调用脚本中的 'up' 函数来应用变更
                        migration_module.up(cursor)
                        # 更新版本号
                        set_version(cursor, version)
                        conn.commit()
                        logger.debug(f"成功应用迁移: {filename}")
                    except Exception as e:
                        conn.rollback()
                        logger.error(f"应用迁移失败: {filename}。错误: {e}")
                        raise
            except Exception as e:
                logger.error(f"加载迁移模块失败: {module_name}。错误: {e}")
                raise

    logger.debug("数据库迁移完成。")
