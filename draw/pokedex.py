import os
from PIL import Image, ImageDraw
from typing import List, Dict, Any
from astrbot.api import logger
from datetime import datetime

from .utils import get_user_avatar, get_fish_icon
from .styles import (
    IMG_WIDTH, PADDING, CORNER_RADIUS,
    COLOR_BACKGROUND, COLOR_HEADER_BG, COLOR_TEXT_WHITE, COLOR_TEXT_DARK,
    COLOR_TEXT_GRAY, COLOR_CARD_BG, COLOR_CARD_BORDER, COLOR_RARITY_MAP,
    FONT_HEADER, FONT_SUBHEADER, FONT_FISH_NAME, FONT_REGULAR, FONT_SMALL,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_GOLD, COLOR_RARE
)

def format_weight(g):
    """将克转换为更易读的单位 (kg, t)"""
    if g is None:
        return "0g"
    if g >= 1000000:
        return f"{g / 1000000:.2f}t"
    if g >= 1000:
        return f"{g / 1000:.2f}kg"
    return f"{g}g"

# --- 布局 ---
HEADER_HEIGHT = 120
FISH_CARD_HEIGHT = 80   # 大幅减小高度以适应20个项目
FISH_CARD_MARGIN = 8    # 减小间距
FISH_PER_PAGE = 20      # 每页显示20个


# 导入优化的渐变生成函数
from .gradient_utils import create_vertical_gradient

def draw_rounded_rectangle(draw, bbox, radius, fill=None, outline=None, width=1):
    """优化的圆角矩形绘制 - 避免边框重叠问题"""
    x1, y1, x2, y2 = bbox
    
    # 首先绘制填充区域（无边框）
    if fill is not None:
        # 主体矩形
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        # 四个圆角
        draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill)
        draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill)
        draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill)
        draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill)
    
    # 然后绘制边框（仅在外围）
    if outline is not None and width > 0:
        # 四条直线边框
        draw.line([x1 + radius, y1, x2 - radius, y1], fill=outline, width=width)  # 上边
        draw.line([x1 + radius, y2, x2 - radius, y2], fill=outline, width=width)  # 下边
        draw.line([x1, y1 + radius, x1, y2 - radius], fill=outline, width=width)  # 左边
        draw.line([x2, y1 + radius, x2, y2 - radius], fill=outline, width=width)  # 右边
        
        # 四个圆角边框
        draw.arc([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=outline, width=width)  # 左上角
        draw.arc([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=outline, width=width)  # 右上角
        draw.arc([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=outline, width=width)   # 左下角
        draw.arc([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=outline, width=width)     # 右下角


async def draw_pokedex(pokedex_data: Dict[str, Any], user_info: Dict[str, Any], output_path: str, page: int = 1, data_dir: str = None):
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
    
    # 创建渐变背景 - 参考背包设计
    bg_top = (174, 214, 241)  # 柔和天蓝色
    bg_bot = (245, 251, 255)  # 温和淡蓝色
    img = create_vertical_gradient(IMG_WIDTH, img_height, bg_top, bg_bot)
    draw = ImageDraw.Draw(img)
    
    # 背包风格的颜色定义
    primary_dark = (52, 73, 94)      # 温和深蓝 - 主标题
    primary_medium = (74, 105, 134)  # 柔和中蓝 - 副标题
    primary_light = (108, 142, 191)  # 淡雅蓝 - 强调色
    text_primary = (55, 71, 79)      # 温和深灰 - 主要文本
    text_secondary = (120, 144, 156) # 柔和灰蓝 - 次要文本
    text_muted = (176, 190, 197)     # 温和浅灰 - 弱化文本
    card_bg = (255, 255, 255, 240)   # 高透明度白色

    # 绘制头部 - 使用背包风格
    draw_rounded_rectangle(draw, (PADDING, PADDING, IMG_WIDTH - PADDING, PADDING + HEADER_HEIGHT), CORNER_RADIUS, fill=card_bg)
    
    # 用户头像和标题区域
    avatar_size = 60
    header_x = PADDING + 30
    header_y = PADDING + 30
    
    # 绘制用户头像 - 参考背包做法
    if data_dir and user_info.get('user_id'):
        if avatar_image := await get_user_avatar(user_info['user_id'], data_dir, avatar_size):
            img.paste(avatar_image, (header_x, header_y), avatar_image)
            header_x += avatar_size + 20  # 头像存在时，标题向右偏移
    
    # 标题 - 使用背包颜色，调整到头像中间位置
    header_text = f"{user_info.get('nickname', '玩家')}的图鉴"
    draw.text((header_x, header_y + 12), header_text, font=FONT_HEADER, fill=primary_dark)

    # 进度 - 使用背包颜色
    progress_text = f"◇ 收集进度: {pokedex_data.get('unlocked_fish_count', 0)} / {pokedex_data.get('total_fish_count', 0)} ◇"
    draw.text((IMG_WIDTH - PADDING - 300, PADDING + 45), progress_text, font=FONT_SUBHEADER, fill=primary_medium)

    # 绘制鱼卡片
    current_y = PADDING + HEADER_HEIGHT + FISH_CARD_MARGIN
    for i, fish in enumerate(page_fishes):
        card_y1 = current_y
        card_y2 = card_y1 + FISH_CARD_HEIGHT
        # 绘制鱼卡片 - 使用背包风格
        draw_rounded_rectangle(draw, (PADDING, card_y1, IMG_WIDTH - PADDING, card_y2), CORNER_RADIUS, fill=card_bg, outline=COLOR_CARD_BORDER)
        # 左侧内容区域
        left_pane_x = PADDING + 30
        
        # 尝试加载并显示鱼类图标
        icon_size = 50
        icon_x = left_pane_x
        icon_y = card_y1 + (FISH_CARD_HEIGHT - icon_size) // 2
        icon_url = fish.get("icon_url")
        if icon_url and data_dir:
            try:
                fish_icon = await get_fish_icon(icon_url, data_dir, icon_size)
                if fish_icon:
                    # 计算图标居中位置
                    icon_x_offset = icon_x
                    icon_y_offset = icon_y
                    img.paste(fish_icon, (icon_x_offset, icon_y_offset), fish_icon)
                    # 调整文本位置，为图标留出空间
                    left_pane_x += icon_size + 15
            except Exception as e:
                logger.warning(f"加载鱼类图标失败: {e}, URL: {icon_url}")
        
        # 鱼名和稀有度 - 调整位置适应更小的卡片
        name_y = card_y1 + 10
        draw.text((left_pane_x, name_y), fish.get("name", "未知鱼"), font=FONT_FISH_NAME, fill=text_primary)
        # 稀有度星星 - 向上移动，使用背包颜色
        rarity_text = "★" * fish.get("rarity", 1)
        rarity = fish.get("rarity", 1)
        # 对于高于5星的鱼，使用稀有红色；对于超过10星的鱼，也使用10星的颜色
        if rarity > 5:
            rarity_color = (220, 20, 60)  # 稀有红色
        else:
            rarity_color = COLOR_RARITY_MAP.get(rarity, text_secondary)
        draw.text((left_pane_x, name_y + 25), rarity_text, font=FONT_FISH_NAME, fill=rarity_color)
        # 右侧统计信息 - 进一步向右移动
        stats_x = PADDING + 440
        stats_y = card_y1 + 15
        # 重量纪录 - 使用更醒目的深金色
        min_w = fish.get('min_weight', 0)
        max_w = fish.get('max_weight', 0)
        weight_text = f"● 重量纪录: 最小 {format_weight(min_w)} / 最大 {format_weight(max_w)}"
        draw.text((stats_x, stats_y), weight_text, font=FONT_REGULAR, fill=(218, 165, 32))  # 深金色
        
        # 累计捕获 - 使用深蓝色
        total_w = fish.get('total_weight', 0)
        caught_text = f"◆ 累计捕获: {fish.get('total_caught', 0)} 条 ({format_weight(total_w)})"
        draw.text((stats_x, stats_y + 18), caught_text, font=FONT_REGULAR, fill=(25, 118, 210))  # 深蓝色

        # 首次捕获 - 使用深绿色
        first_caught_time = fish.get('first_caught_time')
        if isinstance(first_caught_time, datetime):
            first_caught_text = f"★ 首次捕获: {first_caught_time.strftime('%Y-%m-%d %H:%M')}"
        else:
            first_caught_text = f"★ 首次捕获: {str(first_caught_time).split('.')[0] if first_caught_time else '未知'}"
        draw.text((stats_x, stats_y + 36), first_caught_text, font=FONT_REGULAR, fill=(46, 125, 50))  # 深绿色
        # 描述 - 调整位置适应更小的卡片，使用背包颜色
        desc_y = card_y1 + FISH_CARD_HEIGHT - 20
        draw.text((left_pane_x, desc_y), fish.get("description", ""), font=FONT_SMALL, fill=text_muted)

        current_y = card_y2 + FISH_CARD_MARGIN

    # 绘制页脚 - 使用背包颜色
    footer_y = img_height - PADDING - FOOTER_HEIGHT + 20
    footer_text = f"◈ 第 {page} / {total_pages} 页 - 使用 /图鉴 [页码] 查看更多 ◈"
    draw.text((PADDING, footer_y), footer_text, font=FONT_SMALL, fill=text_secondary)

    # 应用整个图片的圆角遮罩
    def apply_rounded_corners(image, corner_radius=20):
        """为整个图片应用圆角"""
        # 创建圆角遮罩
        mask = Image.new("L", image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, image.size[0], image.size[1]], corner_radius, fill=255)
        
        # 创建带透明通道的输出图片
        output = Image.new("RGBA", image.size, (0, 0, 0, 0))
        output.paste(image, (0, 0))
        output.putalpha(mask)
        
        return output

    try:
        logger.info(f"准备将图鉴图片保存至: {output_path}")
        # 应用圆角遮罩
        rounded_img = apply_rounded_corners(img, 20)
        rounded_img.save(output_path)
        logger.info(f"图鉴图片已成功保存至 {output_path}")
    except Exception as e:
        logger.error(f"保存图鉴图片失败: {e}", exc_info=True)
        raise
