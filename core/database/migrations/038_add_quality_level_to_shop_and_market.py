"""
迁移038：为商店和市场系统添加品质支持

- 为 ShopItemReward 表添加 quality_level 字段（鱼类奖励的品质等级）
- 为 MarketListing 表添加 quality_level 字段（市场商品的品质等级）
- 为 ShopItemCost 表添加 quality_level 字段（鱼类成本的品质等级）
- 更新相关的主键和索引
"""

import sqlite3

from astrbot.api import logger


def up(cursor: sqlite3.Cursor):
    """执行迁移"""
    logger.info("正在执行 038_add_quality_level_to_shop_and_market: 为商店和市场系统添加品质支持...")
    
    try:
        # 1. 为 ShopItemReward 表添加 quality_level 字段
        cursor.execute("""
            ALTER TABLE shop_item_rewards 
            ADD COLUMN quality_level INTEGER DEFAULT 0
        """)
        
        # 2. 为 ShopItemCost 表添加 quality_level 字段
        cursor.execute("""
            ALTER TABLE shop_item_costs 
            ADD COLUMN quality_level INTEGER DEFAULT 0
        """)
        
        # 3. 为 MarketListing 表添加 quality_level 字段
        cursor.execute("""
            ALTER TABLE market_listings 
            ADD COLUMN quality_level INTEGER DEFAULT 0
        """)
        
        # 4. 更新 MarketListing 表的主键，包含 quality_level
        # 注意：SQLite 不支持直接修改主键，需要重建表
        cursor.execute("""
            CREATE TABLE market_listings_new (
                market_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                seller_nickname TEXT NOT NULL,
                item_type TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_description TEXT,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,
                listed_at TEXT NOT NULL,
                item_instance_id INTEGER,
                refine_level INTEGER DEFAULT 1,
                quality_level INTEGER DEFAULT 0,
                expires_at TEXT,
                is_anonymous BOOLEAN DEFAULT FALSE,
                UNIQUE(user_id, item_type, item_id, quality_level, item_instance_id)
            )
        """)
        
        # 5. 复制数据到新表
        cursor.execute("""
            INSERT INTO market_listings_new 
            SELECT market_id, user_id, seller_nickname, item_type, item_id, 
                   item_name, item_description, quantity, price, listed_at,
                   item_instance_id, refine_level, 0 as quality_level,
                   expires_at, is_anonymous
            FROM market_listings
        """)
        
        # 6. 删除旧表，重命名新表
        cursor.execute("DROP TABLE market_listings")
        cursor.execute("ALTER TABLE market_listings_new RENAME TO market_listings")
        
        # 7. 创建索引
        cursor.execute("""
            CREATE INDEX idx_market_listings_user_item_quality 
            ON market_listings(user_id, item_type, item_id, quality_level)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_market_listings_item_quality 
            ON market_listings(item_type, item_id, quality_level)
        """)
        
        # 8. 为 ShopItemCost 创建品质相关索引
        cursor.execute("""
            CREATE INDEX idx_shop_item_costs_fish_quality 
            ON shop_item_costs(cost_type, cost_item_id, quality_level) 
            WHERE cost_type = 'fish'
        """)
        
        cursor.connection.commit()
        logger.info("✅ 迁移038完成：为商店和市场系统添加品质支持（包括奖励、成本和市场商品）")
        
    except Exception as e:
        cursor.connection.rollback()
        logger.error(f"❌ 迁移038失败：{e}")
        raise


def down(cursor: sqlite3.Cursor):
    """回滚迁移"""
    logger.info("正在回滚 038_add_quality_level_to_shop_and_market: 移除商店和市场系统的品质支持...")
    
    try:
        # 1. 删除 quality_level 字段（SQLite 不支持直接删除列，需要重建表）
        cursor.execute("""
            CREATE TABLE market_listings_old AS 
            SELECT market_id, user_id, seller_nickname, item_type, item_id, 
                   item_name, item_description, quantity, price, listed_at,
                   item_instance_id, refine_level, expires_at, is_anonymous
            FROM market_listings
        """)
        
        cursor.execute("DROP TABLE market_listings")
        cursor.execute("ALTER TABLE market_listings_old RENAME TO market_listings")
        
        # 2. 删除 ShopItemReward 的 quality_level 字段
        cursor.execute("""
            CREATE TABLE shop_item_rewards_old AS 
            SELECT reward_id, item_id, reward_type, reward_item_id, 
                   reward_quantity, reward_refine_level
            FROM shop_item_rewards
        """)
        
        cursor.execute("DROP TABLE shop_item_rewards")
        cursor.execute("ALTER TABLE shop_item_rewards_old RENAME TO shop_item_rewards")
        
        # 3. 删除 ShopItemCost 的 quality_level 字段
        cursor.execute("""
            CREATE TABLE shop_item_costs_old AS 
            SELECT cost_id, item_id, cost_type, cost_amount, cost_item_id, cost_relation, group_id
            FROM shop_item_costs
        """)
        
        cursor.execute("DROP TABLE shop_item_costs")
        cursor.execute("ALTER TABLE shop_item_costs_old RENAME TO shop_item_costs")
        
        cursor.connection.commit()
        logger.info("✅ 迁移038回滚完成")
        
    except Exception as e:
        cursor.connection.rollback()
        logger.error(f"❌ 迁移038回滚失败：{e}")
        raise
