# draw/styles.py
import os
from PIL import ImageFont

# --- 基础配置 ---
IMG_WIDTH = 800
PADDING = 30
CORNER_RADIUS = 15

# --- 布局定义 ---
HEADER_HEIGHT = 100
USER_CARD_HEIGHT = 90
USER_CARD_MARGIN = 12

# --- 颜色定义 ---
# 基础颜色
COLOR_BACKGROUND = (245, 245, 245)
COLOR_HEADER_BG = (51, 153, 255)
COLOR_TEXT_WHITE = (255, 255, 255)
COLOR_TEXT_DARK = (50, 50, 50)
COLOR_TEXT_GRAY = (120, 120, 140)
COLOR_CARD_BG = (255, 255, 255)
COLOR_CARD_BORDER = (230, 230, 230)
COLOR_ACCENT = (51, 153, 255)

# 状态颜色
COLOR_SUCCESS = (76, 175, 80)      # 温和绿 - 成功/积极状态
COLOR_WARNING = (255, 183, 77)     # 柔和橙 - 警告/中性
COLOR_ERROR = (229, 115, 115)      # 温和红 - 错误/消极状态
COLOR_LOCK = (54, 162, 235)        # 安全蓝 - 锁定保护状态

# 特殊颜色
COLOR_GOLD = (240, 173, 78)        # 温和金色 - 金币
COLOR_RARE = (149, 117, 205)       # 柔和紫色 - 稀有物品

# 排行榜颜色
COLOR_TEXT_GOLD = (255, 215, 0)    # 金色（用于第一名）
COLOR_TEXT_SILVER = (192, 192, 192)  # 银色（用于第二名）
COLOR_TEXT_BRONZE = (205, 127, 50)   # 铜色（用于第三名）
COLOR_FISH_COUNT = (46, 139, 87)     # 鱼数量颜色
COLOR_COINS = (218, 165, 32)         # 金币颜色

# 精炼等级颜色
COLOR_REFINE_RED = (255, 0, 0)     # 红色 - 10级
COLOR_REFINE_ORANGE = (244, 50, 156)  # 粉色 - 6-9级

# 稀有度颜色映射
COLOR_RARITY_MAP = {
    1: (176, 196, 222),  # 1星 钢蓝色
    2: (100, 149, 237),  # 2星 矢车菊蓝
    3: (147, 112, 219),  # 3星 中紫罗兰红
    4: (218, 112, 214),  # 4星 兰花紫
    5: (255, 165, 0),    # 5星 橙色
    6: (255, 69, 0),     # 6星 红橙色
    7: (220, 20, 60),    # 7星 深红色
    8: (178, 34, 34),    # 8星 火砖红
    9: (139, 0, 0),      # 9星 暗红色
    10: (128, 0, 0),     # 10星 栗色
}

# 帮助页面颜色
COLOR_TITLE = (30, 80, 162)        # 标题颜色
COLOR_CMD = (40, 40, 40)           # 命令颜色
COLOR_LINE = (200, 200, 200)       # 分割线颜色
COLOR_SHADOW = (0, 0, 0, 80)       # 阴影颜色

# 装饰颜色
COLOR_CORNER = (255, 255, 255, 80) # 四角装饰颜色

# --- 字体路径 ---
FONT_PATH_BOLD = os.path.join(os.path.dirname(__file__), "resource", "DouyinSansBold.otf")

# --- 字体加载 ---
def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH_BOLD, size)
    except IOError:
        return ImageFont.load_default()

FONT_HEADER = load_font(36)    # 标题字体
FONT_SUBHEADER = load_font(24) # 收集进度字体
FONT_FISH_NAME = load_font(24) # 鱼名字体
FONT_REGULAR = load_font(14)   # 常规字体
FONT_SMALL = load_font(12)     # 小字体