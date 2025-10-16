import os

from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict
from astrbot.api import logger
from .styles import (
    IMG_WIDTH, PADDING, CORNER_RADIUS,
    HEADER_HEIGHT, USER_CARD_HEIGHT, USER_CARD_MARGIN,
    COLOR_BACKGROUND, COLOR_HEADER_BG, COLOR_TEXT_WHITE as COLOR_HEADER_TEXT,
    COLOR_CARD_BG, COLOR_CARD_BORDER, COLOR_TEXT_DARK,
    COLOR_ACCENT, COLOR_TEXT_GOLD, COLOR_TEXT_SILVER, COLOR_TEXT_BRONZE,
    COLOR_FISH_COUNT, COLOR_COINS, load_font
)

def draw_rounded_rectangle(draw, xy, radius=10, fill=None, outline=None, width=1):
    """绘制圆角矩形"""
    x1, y1, x2, y2 = xy
    draw.rectangle((x1+radius, y1, x2-radius, y2), fill=fill, outline=fill)
    draw.rectangle((x1, y1+radius, x2, y2-radius), fill=fill, outline=fill)
    draw.ellipse((x1, y1, x1+2*radius, y1+2*radius), fill=fill, outline=fill)
    draw.ellipse((x2-2*radius, y1, x2, y1+2*radius), fill=fill, outline=fill)
    draw.ellipse((x1, y2-2*radius, x1+2*radius, y2), fill=fill, outline=fill)
    draw.ellipse((x2-2*radius, y2-2*radius, x2, y2), fill=fill, outline=fill)

    if outline:
        draw.arc((x1, y1, x1+2*radius, y1+2*radius), 180, 270, fill=outline, width=width)
        draw.arc((x2-2*radius, y1, x2, y1+2*radius), 270, 360, fill=outline, width=width)
        draw.arc((x1, y2-2*radius, x1+2*radius, y2), 90, 180, fill=outline, width=width)
        draw.arc((x2-2*radius, y2-2*radius, x2, y2), 0, 90, fill=outline, width=width)
        draw.line((x1+radius, y1, x2-radius, y1), fill=outline, width=width)
        draw.line((x1+radius, y2, x2-radius, y2), fill=outline, width=width)
        draw.line((x1, y1+radius, x1, y2-radius), fill=outline, width=width)
        draw.line((x2, y1+radius, x2, y2-radius), fill=outline, width=width)

def get_text_metrics(text, font, draw):
    """获取文本指标，返回边界框和大小"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    return bbox, (text_width, text_height)

def format_large_number(number):
    """将大数字格式化为带单位的字符串（K、M、B等）"""
    if number < 1000:
        return str(number)
    elif number < 1000000:
        return f"{number/1000:.1f}K".replace(".0K", "K")
    elif number < 1000000000:
        return f"{number/1000000:.1f}M".replace(".0M", "M")
    else:
        return f"{number/1000000000:.1f}B".replace(".0B", "B")

# --- 新增：格式化重量的函数 ---
def format_weight(grams):
    """将克(g)格式化为公斤(kg)字符串"""
    if grams < 1000:
        return f"{grams}g"
    kg = grams / 1000
    return f"{kg:.1f}kg".replace(".0kg", "kg")
# --- 新增结束 ---


def draw_fishing_ranking(user_data: List[Dict], output_path: str):
    """
    绘制钓鱼排行榜图片

    参数:
    user_data: 用户数据列表，每个用户是一个字典，包含昵称、称号、金币、钓鱼数量、总重量、鱼竿、饰品等信息
    output_path: 输出图片路径
    """
    # 准备字体
    try:
        font_title = load_font(42)
        font_rank = load_font(32)
        font_name = load_font(22)
        font_regular = load_font(18)
        font_small = load_font(16)
    except IOError:
        logger.warning("指定的字体文件未找到，使用默认字体。")
        font_title = ImageFont.load_default()
        font_rank = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_regular = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # 取前10名用户
    top_users = user_data[:10] if len(user_data) > 10 else user_data

    # 计算图片高度
    total_height = HEADER_HEIGHT + (USER_CARD_HEIGHT + USER_CARD_MARGIN) * len(top_users) + PADDING * 2

    # 创建图片和绘图对象
    img = Image.new("RGB", (IMG_WIDTH, total_height), COLOR_BACKGROUND)
    draw = ImageDraw.Draw(img)

    # 绘制标题区域
    draw_rounded_rectangle(draw, (PADDING, PADDING, IMG_WIDTH - PADDING, PADDING + HEADER_HEIGHT),
                          radius=CORNER_RADIUS, fill=COLOR_HEADER_BG)

    # 绘制标题
    title_text = "钓鱼排行榜 TOP10"
    _, (title_width, title_height) = get_text_metrics(title_text, font_title, draw)
    title_x = (IMG_WIDTH - title_width) // 2
    title_y = PADDING + (HEADER_HEIGHT - title_height) // 2
    draw.text((title_x, title_y), title_text, font=font_title, fill=COLOR_HEADER_TEXT)

    # 绘制用户卡片
    current_y = PADDING + HEADER_HEIGHT + USER_CARD_MARGIN

    # 奖杯符号
    trophy_symbols = []
    try:
        gold_trophy = Image.open(os.path.join(os.path.dirname(__file__),"resource", "gold.png") ).resize((40, 40))
        silver_trophy = Image.open(os.path.join(os.path.dirname(__file__),"resource", "silver.png")).resize((35, 35))
        bronze_trophy = Image.open(os.path.join(os.path.dirname(__file__),"resource", "bronze.png")).resize((35, 35))
        trophy_symbols = [gold_trophy, silver_trophy, bronze_trophy]
    except Exception as e:
        logger.warning(f"加载奖杯图片失败: {e}")
        trophy_symbols = ["1", "2", "3"]

    for idx, user in enumerate(top_users):
        # 获取用户数据
        nickname = user.get("nickname", "未知用户")
        title = user.get("title", "无称号")
        coins = user.get("coins", 0)
        fish_count = user.get("fish_count", 0)
        fishing_rod = user.get("fishing_rod", "普通鱼竿")
        accessory = user.get("accessory", "无饰品")
        # --- 新增：获取总重量数据 ---
        total_weight = user.get("total_weight_caught", 0)

        # 排名颜色
        rank_color = COLOR_TEXT_GOLD if idx == 0 else COLOR_TEXT_SILVER if idx == 1 else COLOR_TEXT_BRONZE if idx == 2 else COLOR_TEXT_DARK

        # 绘制卡片背景
        card_y1 = current_y
        card_y2 = card_y1 + USER_CARD_HEIGHT
        draw_rounded_rectangle(draw,
                              (PADDING, card_y1, IMG_WIDTH - PADDING, card_y2),
                              radius=10,
                              fill=COLOR_CARD_BG,
                              outline=COLOR_CARD_BORDER,
                              width=2)

        # 绘制排名
        rank_x = PADDING + 15
        if idx < 3 and isinstance(trophy_symbols[0], Image.Image):
            trophy_img = trophy_symbols[idx]
            trophy_x = PADDING + 15
            trophy_y = card_y1 + (USER_CARD_HEIGHT - trophy_img.height) // 2
            img.paste(trophy_img, (trophy_x, trophy_y), trophy_img if trophy_img.mode == "RGBA" else None)
        else:
            rank_text = f"#{idx+1}"
            rank_y = card_y1 + (USER_CARD_HEIGHT - get_text_metrics(rank_text, font_rank, draw)[1][1]) // 2
            draw.text((rank_x, rank_y), rank_text, font=font_rank, fill=rank_color)

        # 绘制用户名和称号
        name_x = PADDING + 70
        name_y = card_y1 + 15
        
        if len(nickname) > 12:
            nickname = nickname[:10] + "..."
        draw.text((name_x, name_y), nickname, font=font_name, fill=COLOR_TEXT_DARK)

        _, (name_width, _) = get_text_metrics(nickname, font_name, draw)
        title_x = name_x + name_width + 10
        title_y = name_y + 2
        title_display = title if len(title) <= 8 else title[:6] + ".."
        draw.text((title_x, title_y), f"【{title_display}】", font=font_small, fill=COLOR_ACCENT)

        # --- 修改：重新布局底部信息行 ---
        bottom_line_y = name_y + get_text_metrics(nickname, font_name, draw)[1][1] + 10
        current_x = name_x
        margin = 25 # 各个信息块之间的间距

        # 1. 钓获信息 (数量和总重)
        weight_str = format_weight(total_weight)
        fish_text = f"🎣 钓获: {format_large_number(fish_count)}条 ({weight_str})"
        draw.text((current_x, bottom_line_y), fish_text, font=font_regular, fill=COLOR_FISH_COUNT)
        _, (fish_text_width, _) = get_text_metrics(fish_text, font_regular, draw)
        current_x += fish_text_width + margin

        # 2. 金币信息
        coins_text = f"💰 金币: {format_large_number(coins)}"
        draw.text((current_x, bottom_line_y), coins_text, font=font_regular, fill=COLOR_COINS)
        _, (coins_text_width, _) = get_text_metrics(coins_text, font_regular, draw)
        current_x += coins_text_width + margin

        # 3. 装备信息 (自适应字体大小和截断)
        rod_display = fishing_rod if len(fishing_rod) <= 8 else fishing_rod[:7] + ".."
        acc_display = accessory if len(accessory) <= 8 else accessory[:7] + ".."
        equip_text = f"🛠️ 装备: {rod_display} / {acc_display}"

        # 计算剩余可用宽度
        available_width = IMG_WIDTH - PADDING - 10 - current_x

        # 方案A: 尝试使用常规字体
        _, (equip_text_width, _) = get_text_metrics(equip_text, font_regular, draw)
        if equip_text_width <= available_width:
            draw.text((current_x, bottom_line_y), equip_text, font=font_regular, fill=COLOR_TEXT_DARK)
        else:
            # 方案B: 常规字体太宽，尝试使用小号字体
            _, (small_equip_text_width, _) = get_text_metrics(equip_text, font_small, draw)
            if small_equip_text_width <= available_width:
                # 小号字体能放下，视觉上“变挤了”
                draw.text((current_x, bottom_line_y), equip_text, font=font_small, fill=COLOR_TEXT_DARK)
            else:
                # 方案C: 小号字体也放不下，进行动态截断
                # 从末尾开始逐字减少，直到能放下为止
                temp_text = equip_text
                while len(temp_text) > 0:
                    display_text = temp_text + "..."
                    _, (w, _) = get_text_metrics(display_text, font_small, draw)
                    if w <= available_width:
                        draw.text((current_x, bottom_line_y), display_text, font=font_small, fill=COLOR_TEXT_DARK)
                        break
                    temp_text = temp_text[:-1]
        # --- 修改结束 ---

        # 更新Y坐标
        current_y = card_y2 + USER_CARD_MARGIN

    # 保存图片
    try:
        img.save(output_path)
        logger.info(f"排行榜图片已保存到 {output_path}")
    except Exception as e:
        logger.error(f"保存排行榜图片失败: {e}")
        raise e