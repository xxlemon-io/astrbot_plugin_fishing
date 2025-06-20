import os

from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict
from astrbot.api import logger
# 图片基本设置
IMG_WIDTH = 800
IMG_HEIGHT = 1500  # 动态调整
PADDING = 30  # 减小内边距
CORNER_RADIUS = 15  # 稍微减小圆角

# 颜色定义
COLOR_BACKGROUND = (245, 245, 245)  # 浅灰色背景
COLOR_HEADER_BG = (51, 153, 255)  # 蓝色标题背景
COLOR_HEADER_TEXT = (255, 255, 255)  # 白色标题文字
COLOR_CARD_BG = (255, 255, 255)  # 白色卡片背景
COLOR_CARD_BORDER = (230, 230, 230)  # 灰色卡片边框
COLOR_TEXT_DARK = (50, 50, 50)  # 深灰文字
COLOR_TEXT_GOLD = (255, 215, 0)  # 金色（用于第一名）
COLOR_TEXT_SILVER = (192, 192, 192)  # 银色（用于第二名）
COLOR_TEXT_BRONZE = (205, 127, 50)  # 铜色（用于第三名）
COLOR_ACCENT = (51, 153, 255)  # 强调色
COLOR_FISH_COUNT = (46, 139, 87)  # 鱼数量颜色
COLOR_COINS = (218, 165, 32)  # 更改为更深的金币颜色，提高对比度

# 布局设置
HEADER_HEIGHT = 100  # 减小标题高度
USER_CARD_HEIGHT = 90  # 减小卡片高度
USER_CARD_MARGIN = 12  # 减小卡片间距

# 字体路径 - 请确保这些字体文件存在或使用你系统中的字体
FONT_PATH_REGULAR = os.path.join(os.path.dirname(__file__),"resource", "DouyinSansBold.otf")
FONT_PATH_BOLD = os.path.join(os.path.dirname(__file__),"resource", "DouyinSansBold.otf")

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

def draw_fishing_ranking(user_data: List[Dict], output_path: str = "fishing_ranking.png"):
    """
    绘制钓鱼排行榜图片

    参数:
    user_data: 用户数据列表，每个用户是一个字典，包含昵称、称号、金币、钓鱼数量、鱼竿、饰品等信息
    output_path: 输出图片路径
    """
    # 准备字体
    try:
        font_title = ImageFont.truetype(FONT_PATH_BOLD, 42)  # 减小字体尺寸
        ImageFont.truetype(FONT_PATH_REGULAR, 28)
        font_rank = ImageFont.truetype(FONT_PATH_BOLD, 32)
        ImageFont.truetype(FONT_PATH_BOLD, 36)
        font_name = ImageFont.truetype(FONT_PATH_BOLD, 22)
        font_regular = ImageFont.truetype(FONT_PATH_REGULAR, 18)
        font_small = ImageFont.truetype(FONT_PATH_REGULAR, 16)
    except IOError:
        # 如果找不到指定字体，
        logger.warning("指定的字体文件未找到，使用默认字体。")
        font_title = ImageFont.load_default()
        ImageFont.load_default()
        font_rank = ImageFont.load_default()
        ImageFont.load_default()
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
        gold_trophy = Image.open(os.path.join(os.path.dirname(__file__),"resource", "gold.png") ).resize((40, 40))  # 减小奖杯尺寸
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

        logger.debug(f"绘制用户: {nickname}, 称号: {title}, 金币: {coins}, 钓鱼数量: {fish_count}, 鱼竿: {fishing_rod}, 饰品: {accessory}")

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

        # 绘制排名 - 前三名使用奖杯图标
        rank_x = PADDING + 15  # 减小左侧留白
        rank_y = card_y1 + (USER_CARD_HEIGHT - 36) // 2  # 对所有排名使用相同的垂直中心点

        if idx < 3 and isinstance(trophy_symbols[0], Image.Image):
            # 使用图片奖杯
            trophy_img = trophy_symbols[idx]
            int(rank_y - trophy_img.height/2)
            trophy_x = PADDING + 15
            trophy_y = card_y1 + (USER_CARD_HEIGHT - trophy_img.height) // 2
            # 使用paste方法放置图片
            img.paste(trophy_img, (trophy_x, trophy_y), trophy_img if trophy_img.mode == "RGBA" else None)
        else:
            # 使用数字排名
            rank_text = f"#{idx+1}"
            _, (rank_width, rank_height) = get_text_metrics(rank_text, font_rank, draw)
            draw.text((rank_x, rank_y), rank_text, font=font_rank, fill=rank_color)

        # 绘制用户名和称号
        name_x = PADDING + 70  # 调整用户名位置
        name_y = card_y1 + 15
        # 确保用户名不会太长
        if len(nickname) > 12:
            nickname = nickname[:10] + "..."
        draw.text((name_x, name_y), nickname, font=font_name, fill=COLOR_TEXT_DARK)

        # 称号与用户名同一行，但需要确保不会重叠或超出边界
        _, (name_width, _) = get_text_metrics(nickname, font_name, draw)
        title_x = name_x + name_width + 10
        title_y = name_y + 2
        # 称号长度限制
        title_display = title if len(title) <= 8 else title[:6] + ".."
        draw.text((title_x, title_y), f"【{title_display}】", font=font_small, fill=COLOR_ACCENT)

        # 绘制钓鱼数据
        fish_y = name_y + get_text_metrics(nickname, font_name, draw)[1][1] + 8
        draw.text((name_x, fish_y), f"钓获: {format_large_number(fish_count)}条", font=font_regular, fill=COLOR_FISH_COUNT)

        # 绘制金币（使用更深的金色） - 调整间距
        coins_x = name_x + 140  # 减小间距
        draw.text((coins_x, fish_y), f"金币: {format_large_number(coins)}", font=font_regular, fill=COLOR_COINS)

        # 绘制装备 - 鱼竿放左侧固定位置
        equip_x = coins_x + 140  # 从金币位置算起
        rod_display = fishing_rod if len(fishing_rod) <= 6 else fishing_rod[:5] + ".."
        draw.text((equip_x, fish_y), f"鱼竿: {rod_display}", font=font_regular, fill=COLOR_TEXT_DARK)

        # 饰品标签固定在右侧，保证"饰品:"标签左对齐
        acc_label = "饰品: "
        acc_content = accessory if len(accessory) <= 8 else accessory[:6] + ".."
        _, (acc_label_width, _) = get_text_metrics(acc_label, font_regular, draw)
        _, (acc_content_width, _) = get_text_metrics(acc_content, font_regular, draw)

        # 饰品标签固定在右侧，保证"饰品:"标签左对齐
        acc_label_x = IMG_WIDTH - PADDING - 180  # 固定的"饰品:"标签左对齐位置
        acc_label = "饰品: "
        acc_content = accessory if len(accessory) <= 8 else accessory[:6] + ".."

        # 确保不会与鱼竿重叠，设置最小距离
        rod_text = f"鱼竿: {rod_display}"
        _, (rod_width, _) = get_text_metrics(rod_text, font_regular, draw)
        min_acc_label_x = equip_x + rod_width + 60  # 至少保持60像素的间距

        # 如果计算出的位置太靠左，会与鱼竿重叠，则使用最小位置
        acc_label_x = max(acc_label_x, min_acc_label_x)

        # 绘制标签和内容
        draw.text((acc_label_x, fish_y), f"饰品: {acc_content}", font=font_regular, fill=COLOR_TEXT_DARK)

        # 更新Y坐标
        current_y = card_y2 + USER_CARD_MARGIN

    # 保存图片
    try:
        img.save(output_path)
        logger.info(f"排行榜图片已保存到 {output_path}")
    except Exception as e:
        logger.error(f"保存排行榜图片失败: {e}")
        raise e
