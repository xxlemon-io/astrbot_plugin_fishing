import os
from PIL import Image, ImageDraw
from typing import List, Dict, Any
from astrbot.api import logger

from .utils import get_user_avatar
from .styles import (
    IMG_WIDTH, PADDING, CORNER_RADIUS,
    COLOR_BACKGROUND, COLOR_HEADER_BG, COLOR_TEXT_WHITE, COLOR_TEXT_DARK,
    COLOR_TEXT_GRAY, COLOR_CARD_BG, COLOR_CARD_BORDER, COLOR_RARITY_MAP,
    FONT_HEADER, FONT_SUBHEADER, FONT_FISH_NAME, FONT_REGULAR, FONT_SMALL
)

# --- 布局 ---
HEADER_HEIGHT = 120
FISH_CARD_HEIGHT = 150
FISH_CARD_MARGIN = 20
FISH_PER_PAGE = 5


def draw_rounded_rectangle(draw, xy, radius, fill, outline=None, width=1):
    """通用圆角矩形绘制"""
    x1, y1, x2, y2 = xy
    draw.rectangle(xy, fill=fill, outline=outline)


def draw_pokedex(pokedex_data: Dict[str, Any], user_info: Dict[str, Any], output_path: str, page: int = 1):
    """
    绘制图鉴图片
    """
    pokedex_list = pokedex_data.get("pokedex", [])
    total_pages = (len(pokedex_list) + FISH_PER_PAGE - 1) // FISH_PER_PAGE
    start_index = (page - 1) * FISH_PER_PAGE
    end_index = start_index + FISH_PER_PAGE
    page_fishes = pokedex_list[start_index:end_index]

    # 页脚高度
    FOOTER_HEIGHT = 50
    img_height = HEADER_HEIGHT + (FISH_CARD_HEIGHT + FISH_CARD_MARGIN) * len(page_fishes) + PADDING * 2 + FOOTER_HEIGHT
    img = Image.new("RGB", (IMG_WIDTH, img_height), COLOR_BACKGROUND)
    draw = ImageDraw.Draw(img)

    # 绘制头部
    draw_rounded_rectangle(draw, (PADDING, PADDING, IMG_WIDTH - PADDING, PADDING + HEADER_HEIGHT), CORNER_RADIUS, fill=COLOR_HEADER_BG)
    
    # 标题
    header_text = f"{user_info.get('nickname', '玩家')}的图鉴"
    draw.text((PADDING + 30, PADDING + 30), header_text, font=FONT_HEADER, fill=COLOR_TEXT_WHITE)

    # 进度
    progress_text = f"收集进度: {pokedex_data.get('unlocked_fish_count', 0)} / {pokedex_data.get('total_fish_count', 0)}"
    draw.text((IMG_WIDTH - PADDING - 300, PADDING + 45), progress_text, font=FONT_SUBHEADER, fill=COLOR_TEXT_WHITE)

    # 绘制鱼卡片
    current_y = PADDING + HEADER_HEIGHT + FISH_CARD_MARGIN
    for fish in page_fishes:
        card_y1 = current_y
        card_y2 = card_y1 + FISH_CARD_HEIGHT
        draw_rounded_rectangle(draw, (PADDING, card_y1, IMG_WIDTH - PADDING, card_y2), CORNER_RADIUS, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER)
        # 左侧内容区域
        left_pane_x = PADDING + 30
        # 鱼名和稀有度
        name_y = card_y1 + 20
        draw.text((left_pane_x, name_y), fish.get("name", "未知鱼"), font=FONT_FISH_NAME, fill=COLOR_TEXT_DARK)
        # 稀有度星星
        rarity_text = "★" * fish.get("rarity", 1)
        rarity_color = COLOR_RARITY_MAP.get(fish.get("rarity", 1), COLOR_TEXT_GRAY)
        draw.text((left_pane_x, name_y + 40), rarity_text, font=FONT_FISH_NAME, fill=rarity_color)
        # 右侧统计信息
        stats_x = PADDING + 300
        stats_y = card_y1 + 25
        # 重量纪录
        weight_text = f"⚖️ 重量纪录: {fish.get('min_weight', 0)}g / {fish.get('max_weight', 0)}g"
        draw.text((stats_x, stats_y), weight_text, font=FONT_REGULAR, fill=COLOR_TEXT_GRAY)
        # 累计捕获
        caught_text = f"📈 累计捕获: {fish.get('total_caught', 0)} 条 ({fish.get('total_weight', 0)}g)"
        draw.text((stats_x, stats_y + 30), caught_text, font=FONT_REGULAR, fill=COLOR_TEXT_GRAY)
        # 首次捕获
        first_caught_text = f"🗓️ 首次捕获: {fish.get('first_caught_time', '未知')}"
        draw.text((stats_x, stats_y + 60), first_caught_text, font=FONT_REGULAR, fill=COLOR_TEXT_GRAY)
        # 描述
        desc_y = card_y1 + FISH_CARD_HEIGHT - 35
        draw.text((left_pane_x, desc_y), fish.get("description", ""), font=FONT_SMALL, fill=COLOR_TEXT_GRAY)

        current_y = card_y2 + FISH_CARD_MARGIN

    # 绘制页脚
    footer_y = img_height - PADDING - FOOTER_HEIGHT + 20
    footer_text = f"第 {page} / {total_pages} 页 - 使用 /图鉴 [页码] 查看更多"
    draw.text((PADDING, footer_y), footer_text, font=FONT_SMALL, fill=COLOR_TEXT_GRAY)

    try:
        img.save(output_path)
        logger.info(f"图鉴图片已保存至 {output_path}")
    except Exception as e:
        logger.error(f"保存图鉴图片失败: {e}")
        raise
