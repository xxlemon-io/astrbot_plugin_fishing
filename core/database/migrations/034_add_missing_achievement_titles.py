
import sqlite3
from astrbot.api import logger

# --- 配置区 ---

# 定义本次迁移需要新增的称号数据
# 格式: ('title_id', 'name', 'description', 'display_format')
NEW_TITLES_TO_ADD = [
    # 请在这里添加所有您因为 FOREIGN KEY 错误而需要补充的称号
    # 例如，如果您的 'WipeBomb100xMultiplier' 成就奖励的 title_id 是 'lucky_star'，就应该写成：
    (20, "Lucky☆Star", "在擦弹中获得100倍奖励", "{username}, Lucky☆Star"),
    (21, "計画通り", "在擦弹中获得200倍奖励", "{username}, 一切尽在掌握!"),
    (22, "这就是我的逃跑路线！", "在擦弹中获得500倍奖励", "{username}, 这就是我的逃跑路线！"),
    (23, "超高校级的幸运", "在擦弹中获得1000倍奖励", "{username}, 超高校级的幸运!"),
    (24, "「 」", "在擦弹中获得1500倍奖励", "{username}, NO GAME NO LIFE!"),
    (25, "杂鱼~杂鱼~", "在擦弹中获得0.001倍奖励", "{username}, 杂鱼~杂鱼~"),
    
    # 如果还有其他称号想在这次一起添加，可以继续在这里加新行
    # ('wipe_bomb_master', '擦弹大师', '在擦弹中展现出神入化技巧的证明。', '【擦弹大师】{nickname}'),
]

def up(cursor: sqlite3.Cursor):
    """
    应用此迁移：向 titles 表中添加缺失的、用于成就奖励的称号。
    """
    logger.debug("正在执行 034_add_missing_achievement_titles: 添加缺失的成就称号...")

    try:
        # 使用 executemany 和 INSERT OR IGNORE 可以高效、安全地插入多条数据
        # 如果 title_id 已存在，它会自动跳过，不会报错
        cursor.executemany(
            "INSERT OR IGNORE INTO titles (title_id, name, description, display_format) VALUES (?, ?, ?, ?)",
            NEW_TITLES_TO_ADD
        )
        
        # rowcount 会返回受影响的行数，可以用来判断是否真的插入了新数据
        if cursor.rowcount > 0:
            logger.info(f"成功向 'titles' 表添加了 {cursor.rowcount} 个新称号。")
        else:
            logger.info("所有待添加的称号均已存在于 'titles' 表中，无需操作。")

    except sqlite3.Error as e:
        logger.error(f"在迁移 034_add_missing_achievement_titles 期间发生错误: {e}")
        # 将错误向上抛出，让迁移运行器知道此次迁移失败了
        raise