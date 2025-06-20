import sqlite3

from astrbot.api import logger


def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：创建项目所需的全部初始表和索引。
    """
    logger.debug("正在执行 001_initial_setup: 创建所有初始表...")

    # --- 配置表 (Configuration Tables) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fish (
            fish_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT,
            rarity INTEGER NOT NULL CHECK (rarity >= 1 AND rarity <= 5), base_value INTEGER NOT NULL,
            min_weight INTEGER NOT NULL CHECK (min_weight >= 0), max_weight INTEGER NOT NULL CHECK (max_weight > min_weight),
            icon_url TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS baits (
            bait_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT,
            rarity INTEGER NOT NULL DEFAULT 1 CHECK (rarity >= 1), effect_description TEXT,
            duration_minutes INTEGER DEFAULT 0, cost INTEGER DEFAULT 0, required_rod_rarity INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rods (
            rod_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT,
            rarity INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL CHECK (source IN ('shop', 'gacha', 'event')),
            purchase_cost INTEGER, bonus_fish_quality_modifier REAL DEFAULT 1.0,
            bonus_fish_quantity_modifier REAL DEFAULT 1.0, bonus_rare_fish_chance REAL DEFAULT 0.0,
            durability INTEGER, icon_url TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accessories (
            accessory_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT,
            rarity INTEGER NOT NULL DEFAULT 1, slot_type TEXT DEFAULT 'general' NOT NULL,
            bonus_fish_quality_modifier REAL DEFAULT 1.0, bonus_fish_quantity_modifier REAL DEFAULT 1.0,
            bonus_rare_fish_chance REAL DEFAULT 0.0, bonus_coin_modifier REAL DEFAULT 1.0,
            other_bonus_description TEXT, icon_url TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS titles (
            title_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL,
            display_format TEXT DEFAULT '{name}'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gacha_pools (
            gacha_pool_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT,
            cost_coins INTEGER DEFAULT 0, cost_premium_currency INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gacha_pool_items (
            gacha_pool_item_id INTEGER PRIMARY KEY AUTOINCREMENT, gacha_pool_id INTEGER NOT NULL,
            item_type TEXT NOT NULL CHECK (item_type IN ('rod', 'accessory', 'bait', 'fish', 'coins', 'premium_currency')),
            item_id INTEGER NOT NULL, quantity INTEGER DEFAULT 1,
            weight INTEGER NOT NULL CHECK (weight > 0),
            FOREIGN KEY (gacha_pool_id) REFERENCES gacha_pools(gacha_pool_id) ON DELETE CASCADE
        )
    """)

    # --- 用户数据与日志表 (User Data & Log Tables) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY, nickname TEXT, coins INTEGER DEFAULT 200,
            premium_currency INTEGER DEFAULT 0, total_fishing_count INTEGER DEFAULT 0,
            total_weight_caught INTEGER DEFAULT 0, total_coins_earned INTEGER DEFAULT 0,
            equipped_rod_instance_id INTEGER, equipped_accessory_instance_id INTEGER,
            current_bait_id INTEGER, bait_start_time DATETIME, current_title_id INTEGER,
            auto_fishing_enabled INTEGER DEFAULT 0, last_fishing_time DATETIME,
            last_wipe_bomb_time DATETIME, last_steal_time DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP, last_login_time DATETIME,
            consecutive_login_days INTEGER DEFAULT 0, fish_pond_capacity INTEGER DEFAULT 480,
            last_stolen_at DATETIME
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_achievement_progress (
            user_id TEXT NOT NULL, achievement_id INTEGER NOT NULL, current_progress INTEGER DEFAULT 0,
            completed_at DATETIME, claimed_at DATETIME,
            PRIMARY KEY (user_id, achievement_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_fish_inventory (
            user_id TEXT NOT NULL, fish_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 0 CHECK (quantity >= 0),
            no_sell_until DATETIME,
            PRIMARY KEY (user_id, fish_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (fish_id) REFERENCES fish(fish_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_bait_inventory (
            user_id TEXT NOT NULL, bait_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 0 CHECK (quantity >= 0),
            PRIMARY KEY (user_id, bait_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (bait_id) REFERENCES baits(bait_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_rods (
            rod_instance_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
            rod_id INTEGER NOT NULL, obtained_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            current_durability INTEGER, is_equipped INTEGER DEFAULT 0 CHECK (is_equipped IN (0, 1)),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (rod_id) REFERENCES rods(rod_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_accessories (
            accessory_instance_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
            accessory_id INTEGER NOT NULL, obtained_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_equipped INTEGER DEFAULT 0 CHECK (is_equipped IN (0, 1)),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (accessory_id) REFERENCES accessories(accessory_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_titles (
            user_id TEXT NOT NULL, title_id INTEGER NOT NULL,
            unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, title_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (title_id) REFERENCES titles(title_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fishing_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, fish_id INTEGER NOT NULL,
            weight INTEGER NOT NULL, value INTEGER NOT NULL, rod_instance_id INTEGER,
            accessory_instance_id INTEGER, bait_id INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            location_id INTEGER, is_king_size INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (fish_id) REFERENCES fish(fish_id) ON DELETE RESTRICT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gacha_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, gacha_pool_id INTEGER NOT NULL,
            item_type TEXT NOT NULL, item_id INTEGER NOT NULL, item_name TEXT NOT NULL,
            quantity INTEGER DEFAULT 1, rarity INTEGER DEFAULT 1, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (gacha_pool_id) REFERENCES gacha_pools(gacha_pool_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wipe_bomb_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
            contribution_amount INTEGER NOT NULL, reward_multiplier REAL NOT NULL,
            reward_amount INTEGER NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS check_ins (
            user_id TEXT NOT NULL, check_in_date DATE NOT NULL,
            PRIMARY KEY (user_id, check_in_date),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market (
            market_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
            item_type TEXT NOT NULL CHECK (item_type IN ('rod', 'accessory')),
            item_id INTEGER NOT NULL, quantity INTEGER NOT NULL CHECK (quantity > 0),
            price INTEGER NOT NULL CHECK (price > 0),
            listed_at DATETIME DEFAULT CURRENT_TIMESTAMP, expires_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS taxes (
            tax_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
            tax_amount INTEGER NOT NULL, tax_rate REAL NOT NULL, original_amount INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, tax_type TEXT NOT NULL,
            balance_after INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # --- 索引 (Indices) ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_coins ON users(coins)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_fish_inventory_user ON user_fish_inventory(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_bait_inventory_user ON user_bait_inventory(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_rods_user ON user_rods(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_accessories_user ON user_accessories(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_titles_user ON user_titles(user_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_achievement_progress_user ON user_achievement_progress(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wipe_bomb_log_user_time ON wipe_bomb_log(user_id, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fishing_records_user_time ON fishing_records(user_id, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fishing_records_fish_id ON fishing_records(fish_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_gacha_pool_items_pool_type ON gacha_pool_items(gacha_pool_id, item_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gacha_records_user_time ON gacha_records(user_id, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_user ON market(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_item ON market(item_type, item_id)")

    logger.info("001_initial_setup: 所有表和索引创建完成。")
