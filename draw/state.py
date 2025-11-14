import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from io import BytesIO
import time
import json
from .utils import get_user_avatar
from .styles import (
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_GOLD, COLOR_RARE,
    COLOR_REFINE_RED, COLOR_REFINE_ORANGE, COLOR_CORNER, load_font
)
from .text_utils import load_font_with_cjk_fallback, draw_text_smart

def format_rarity_display(rarity: int) -> str:
    """格式化稀有度显示，支持显示到10星，10星以上显示为★★★★★★★★★★+"""
    if rarity <= 10:
        return '★' * rarity
    else:
        return '★★★★★★★★★★+'

async def draw_state_image(user_data: Dict[str, Any], data_dir: str) -> Image.Image:
    """
    绘制用户状态图像
    
    Args:
        user_data: 包含用户状态信息的字典，    # 定义状态信息的网格位置
    status_col_x = card_margin + 15
    status_row1_y = current_y + 12
    status_row2_y = current_y + 35
    status_row3_y = current_y + 58

    # 自动钓鱼状态
    auto_fishing = user_data.get('auto_fishing_enabled', False)
    if auto_fishing:
        auto_text = "自动钓鱼: 已开启"
        auto_color = positive_color
    else:
        auto_text = "自动钓鱼: 已关闭"
        auto_color = negative_color
    draw.text((status_col_x, status_row1_y), auto_text, font=content_font, fill=auto_color)      - user_id: 用户ID
            - nickname: 用户昵称
            - coins: 金币数量
            - current_rod: 当前装备的鱼竿信息
            - current_accessory: 当前装备的饰品信息
            - current_bait: 当前装备的鱼饵信息
            - auto_fishing_enabled: 是否开启自动钓鱼
            - steal_cooldown_remaining: 偷鱼剩余CD时间（秒）
            - fishing_zone: 当前钓鱼区域
            - current_title: 当前称号信息
            - total_fishing_count: 总钓鱼次数
            - steal_total_value: 偷鱼总价值 TODO
            - signed_in_today: 今日是否签到
            - wipe_bomb_remaining: 擦弹剩余次数
            - electric_fish_cooldown_remaining: 电鱼剩余CD时间（秒）
            - wof_remaining_plays: 命运之轮剩余次数
            - pond_info: 鱼塘信息
    Returns:
        PIL.Image.Image: 生成的状态图像
    """
    # 画布尺寸 
    width, height = 620, 540
    
    # 导入优化的渐变生成函数
    from .gradient_utils import create_vertical_gradient

    bg_top = (174, 214, 241)  # 柔和天蓝色
    bg_bot = (245, 251, 255)  # 温和淡蓝色
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)

    # 2. 加载字体（称号字体使用CJK回退支持）
    def load_font(name, size):
        path = os.path.join(os.path.dirname(__file__), "resource", name)
        try:
            return ImageFont.truetype(path, size)
        except Exception as e:
            return ImageFont.load_default()

    font_path = os.path.join(os.path.dirname(__file__), "resource", "DouyinSansBold.otf")
    title_font = load_font("DouyinSansBold.otf", 28)
    subtitle_font = load_font("DouyinSansBold.otf", 24)
    content_font = load_font("DouyinSansBold.otf", 20)
    # 称号字体使用CJK回退支持，确保繁体中文能正确显示
    small_font = load_font_with_cjk_fallback(font_path, 16)
    tiny_font = load_font("DouyinSansBold.otf", 14)

    # 3. 颜色定义 - 温和协调的海洋主题配色
    # 主色调：柔和蓝系
    primary_dark = (52, 73, 94)      # 温和深蓝 - 主标题
    primary_medium = (74, 105, 134)  # 柔和中蓝 - 副标题
    primary_light = (108, 142, 191)  # 淡雅蓝 - 强调色
    
    # 文本色：和谐灰蓝色系
    text_primary = (55, 71, 79)      # 温和深灰 - 主要文本
    text_secondary = (120, 144, 156) # 柔和灰蓝 - 次要文本
    text_muted = (176, 190, 197)     # 温和浅灰 - 弱化文本
    
    # 状态色：柔和自然色系
    success_color = COLOR_SUCCESS
    warning_color = COLOR_WARNING
    error_color = COLOR_ERROR
    
    # 背景色：更柔和的对比
    card_bg = (255, 255, 255, 240)   # 高透明度白色
    
    # 特殊色：温和特色
    gold_color = COLOR_GOLD
    rare_color = COLOR_RARE

    # 4. 获取文本尺寸的辅助函数
    def get_text_size(text, font):
        # 如果是FontWithFallback类型，使用主字体测量（简化处理）
        actual_font = font.primary_font if hasattr(font, 'primary_font') else font
        bbox = draw.textbbox((0, 0), text, font=actual_font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    # 5. 绘制圆角矩形
    def draw_rounded_rectangle(draw, bbox, radius, fill=None, outline=None, width=1):
        x1, y1, x2, y2 = bbox
        # 绘制主体矩形
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill, outline=outline, width=width)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill, outline=outline, width=width)
        # 绘制圆角
        draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill, outline=outline, width=width)
        draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill, outline=outline, width=width)
        draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill, outline=outline, width=width)
        draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill, outline=outline, width=width)

    # 绘制标题
    title_text = "用户状态面板"
    title_w, title_h = get_text_size(title_text, title_font)
    title_x = (width - title_w) // 2
    title_y = 20
    draw.text((title_x, title_y), title_text, font=title_font, fill=primary_dark)

    # 用户基本信息卡片
    current_y = title_y + title_h + 15
    card_height = 85
    card_margin = 15
    
    # 用户信息卡片
    draw_rounded_rectangle(draw, 
                         (card_margin, current_y, width - card_margin, current_y + card_height), 
                         10, fill=card_bg)
    
    # 列位置
    col1_x_without_avatar = card_margin + 20  # 第一列
    avatar_size = 60
    col1_x_with_avatar = col1_x_without_avatar + avatar_size + 20  # 有头像时偏移
    col1_x = col1_x_without_avatar # 默认无头像
    col2_x = col1_x + 240 # 第二列位置
    
    # 行位置
    row1_y = current_y + 12
    row2_y = current_y + 52

    # 绘制用户头像 - 如有
    if user_id := user_data.get('user_id'):
        if avatar_image := await get_user_avatar(user_id, data_dir, avatar_size):
            image.paste(avatar_image, (col1_x, row1_y), avatar_image)
            col1_x = col1_x_with_avatar # 更新 col1_x 以适应头像位置

    
    # 用户昵称
    nickname = user_data.get('nickname', '未知用户')
    nickname_text = f"{nickname}"
    draw.text((col1_x, row1_y), nickname_text, font=subtitle_font, fill=primary_medium)
    
  

    # 当前称号,跟在用户昵称后面
    current_title = user_data.get('current_title')
    nickname_width = get_text_size(nickname_text, subtitle_font)[0]
    height_offset = 5
    if current_title:
        if isinstance(current_title, dict):
            title_text = f"{current_title.get('name', '未知称号')}"
        else:
            title_text = f"{current_title}"

        # 使用智能文本绘制，自动处理繁体中文等缺失字符
        draw_text_smart(
            draw,
            (col1_x + nickname_width + 10, row1_y + height_offset),
            title_text,
            small_font,
            rare_color
        )
    # else:
    #     title_text = "未装备
    #     draw.text((col1_x + nickname_width + 10, row1_y + height_offset), title_text, font=small_font, fill=text_color)
    
    # 金币
    coins = user_data.get('coins', 0)
    coins_text = f"金币: {coins:,}"
    draw.text((col1_x, row2_y - 12), coins_text, font=small_font, fill=gold_color)
    
    # 高级货币（另起一行，避免与右侧“钓鱼次数”重叠）
    if 'premium_currency' in user_data:
        premium = user_data.get('premium_currency', 0)
        premium_text = f"高级货币: {premium:,}"
        # 另起新行显示并整体上移，避免超出白色卡片底部
        draw.text((col1_x, row2_y + 8), premium_text, font=small_font, fill=primary_light)
    
    # 钓鱼次数 - 调整列位置以均分
    total_fishing = user_data.get('total_fishing_count', 0)
    fishing_text = f"钓鱼次数: {total_fishing:,}"
    draw.text((col2_x, row2_y), fishing_text, font=small_font, fill=text_primary)

    # 偷鱼总价值 - 调整列位置以均分 TODO
    # steal_total = user_data.get('steal_total_value', 0)
    # steal_text = f"偷鱼获金: {steal_total:,}"
    # col3_adjusted_x = card_margin + (width - card_margin * 2) * 2 // 3 + card_margin
    # draw.text((col3_adjusted_x, row2_y), steal_text, font=small_font, fill=warning_color)

    # 装备信息区域
    current_y += card_height + 5
    equipment_title = "当前装备"
    draw.text((card_margin, current_y), equipment_title, font=subtitle_font, fill=primary_medium)
    current_y += 30

    # 装备卡片 - 两列等宽布局
    equipment_card_height = 130
    card_width = (width - card_margin * 2 - 15) // 2
    
    # 左列：鱼竿和饰品
    left_card_x = card_margin
    draw_rounded_rectangle(draw, 
                         (left_card_x, current_y, left_card_x + card_width, current_y + equipment_card_height), 
                         8, fill=card_bg)

    # 定义左列的布局位置
    left_col_x = left_card_x + 12
    equipment_row1_y = current_y + 10
    equipment_row2_y = current_y + 30
    equipment_row3_y = current_y + 50
    equipment_row4_y = current_y + 70
    equipment_row5_y = current_y + 90
    equipment_row6_y = current_y + 110

    # 鱼竿标题
    draw.text((left_col_x, equipment_row1_y), "鱼竿", font=small_font, fill=primary_light)
    
    # 鱼竿内容
    current_rod = user_data.get('current_rod')
    if current_rod:
        rod_name = current_rod['name'][:15] + "..." if len(current_rod['name']) > 15 else current_rod['name']
        
        # 先获取耐久度信息用于显示
        current_dur = current_rod.get('current_durability')
        max_dur = current_rod.get('max_durability')
        
        # 在鱼竿名称右边显示耐久度
        if max_dur is not None and current_dur is not None:
            # 有限耐久装备
            durability_text = f" (耐久: {current_dur}/{max_dur})"
            # 根据耐久度设置颜色 - 使用与整体设计一致的颜色系统
            durability_ratio = current_dur / max_dur if max_dur > 0 else 0
            if durability_ratio > 0.6:
                dur_color = success_color  # 使用成功色 - 温和绿
            elif durability_ratio > 0.3:
                dur_color = warning_color  # 使用警告色 - 柔和橙
            else:
                dur_color = error_color    # 使用错误色 - 温和红
        elif current_dur is None:
            # 无限耐久装备
            durability_text = " (无限耐久)"
            dur_color = primary_light     # 使用主色调 - 淡雅蓝，与UI风格一致
        else:
            durability_text = ""
            dur_color = text_primary
        
        # 显示鱼竿名称
        draw.text((left_col_x, equipment_row2_y), rod_name, font=content_font, fill=text_primary)
        
        # 在鱼竿名称右边显示耐久度
        if durability_text:
            rod_name_width = get_text_size(rod_name, content_font)[0]
            durability_x = left_col_x + rod_name_width + 5  # 5像素间隔
            draw.text((durability_x, equipment_row2_y), durability_text, font=tiny_font, fill=dur_color)
        
        # 根据稀有度和精炼等级选择颜色
        rarity = current_rod.get('rarity', 1)
        refined_level = current_rod.get('refine_level', 1)
        if refined_level >= 10:
            star_color = COLOR_REFINE_RED  # 红色 - 10级
        elif refined_level >= 6:
            star_color = COLOR_REFINE_ORANGE  # 橙色 - 6-9级
        elif rarity > 4 and refined_level > 4:
            star_color = rare_color
        elif rarity > 3:
            star_color = warning_color
        else:
            star_color = text_secondary
        
        # 稀有度和精炼等级显示
        rarity_refine_text = f"{format_rarity_display(rarity)} Lv.{refined_level}"
        draw.text((left_col_x, equipment_row3_y), rarity_refine_text, font=tiny_font, fill=star_color)
    else:
        draw.text((left_col_x, equipment_row2_y), "未装备", font=content_font, fill=text_muted)

    # 饰品标题
    draw.text((left_col_x, equipment_row4_y), "饰品", font=small_font, fill=primary_light)
    
    # 饰品内容
    current_accessory = user_data.get('current_accessory')
    if current_accessory:
        acc_name = current_accessory['name'][:15] + "..." if len(current_accessory['name']) > 15 else current_accessory['name']
        draw.text((left_col_x, equipment_row5_y), acc_name, font=content_font, fill=text_primary)
        rarity = current_accessory.get('rarity', 1)
        refined_level = current_accessory.get('refine_level', 1)
        if refined_level >= 10:
            star_color = COLOR_REFINE_RED  # 红色 - 10级
        elif refined_level >= 6:
            star_color = COLOR_REFINE_ORANGE  # 橙色 - 6-9级
        elif rarity > 4 and refined_level > 4:
            star_color = rare_color
        elif rarity > 3:
            star_color = warning_color
        else:
            star_color = text_secondary
        draw.text((left_col_x, equipment_row6_y), f"{format_rarity_display(rarity)} Lv.{refined_level}", font=tiny_font, fill=star_color)
    else:
        draw.text((left_col_x, equipment_row5_y), "未装备", font=content_font, fill=text_muted)

    # 右列：鱼饵和区域
    right_card_x = left_card_x + card_width + 15
    draw_rounded_rectangle(draw, 
                         (right_card_x, current_y, right_card_x + card_width, current_y + equipment_card_height), 
                         8, fill=card_bg)

    # 定义右列的布局位置
    right_col_x = right_card_x + 12

    # 鱼饵标题
    draw.text((right_col_x, equipment_row1_y), "鱼饵", font=small_font, fill=primary_light)
    
    # 鱼饵内容
    current_bait = user_data.get('current_bait')
    if current_bait:
        bait_name = current_bait['name'][:15] + "..." if len(current_bait['name']) > 15 else current_bait['name']
        draw.text((right_col_x, equipment_row2_y), bait_name, font=content_font, fill=text_primary)
        rarity = current_bait.get('rarity', 1)
        star_color = rare_color if rarity > 4 else warning_color if rarity >= 3 else text_secondary
        bait_detail = f"{format_rarity_display(rarity)} 剩余：{current_bait.get('quantity', 0)}"
        draw.text((right_col_x, equipment_row3_y), bait_detail, font=tiny_font, fill=star_color)
    else:
        draw.text((right_col_x, equipment_row2_y), "未使用", font=content_font, fill=text_muted)

    # 钓鱼区域标题
    draw.text((right_col_x, equipment_row4_y), "钓鱼区域", font=small_font, fill=primary_light)
    
    # 钓鱼区域内容
    fishing_zone = user_data.get('fishing_zone', {})
    zone_name = fishing_zone.get('name', '未知区域')
    zone_display = zone_name[:12] + "..." if len(zone_name) > 12 else zone_name
    draw.text((right_col_x, equipment_row5_y), zone_display, font=content_font, fill=text_primary)
    if fishing_zone.get('rare_fish_quota', 0) == 0:
        zone_detail = "此区域无稀有鱼"
        detail_color = text_muted
    elif fishing_zone.get('rare_fish_quota', 0) - fishing_zone.get('rare_fish_caught', 0) > 0:
        zone_detail = f"剩余稀有鱼：{fishing_zone.get('rare_fish_quota', 0) - fishing_zone.get('rare_fish_caught', 0)}条"
        detail_color = success_color
    else:
        zone_detail = "今日稀有鱼已捕完"
        detail_color = text_muted
    draw.text((right_col_x, equipment_row6_y), zone_detail, font=tiny_font, fill=detail_color)

    # 状态信息区域 - 合并今日状态和钓鱼状态
    current_y += equipment_card_height + 5
    status_title = "状态信息"
    draw.text((card_margin, current_y), status_title, font=subtitle_font, fill=primary_medium)
    current_y += 30

    # 状态卡片 - 扩展高度容纳更多信息
    status_card_height = 120
    draw_rounded_rectangle(draw, 
                         (card_margin, current_y, width - card_margin, current_y + status_card_height), 
                         8, fill=card_bg)

    # 定义状态信息的网格位置 - 多行两列布局
    status_col1_x = card_margin + 15    # 左列
    status_col2_x = card_margin + 315   # 右列
    status_row1_y = current_y + 12      # 第一行
    status_row2_y = current_y + 35      # 第二行
    status_row3_y = current_y + 58      # 第三行
    status_row4_y = current_y + 81      # 第四行 (鱼塘信息)

    # 左列第一行：签到状态
    signed_today = user_data.get('signed_in_today', False)
    if signed_today:
        sign_text = "今日签到: 已签到"
        sign_color = success_color
    else:
        sign_text = "今日签到: 未签到" 
        sign_color = error_color
    draw.text((status_col1_x, status_row1_y), sign_text, font=content_font, fill=sign_color)

    # 右列第一行：擦弹次数
    wipe_remaining = user_data.get('wipe_bomb_remaining', 0)
    if wipe_remaining > 0:
        wipe_text = f"擦弹次数: 剩余 {wipe_remaining} 次"
        wipe_color = error_color
    else:
        wipe_text = "擦弹次数: 已用完"
        wipe_color = text_muted
    draw.text((status_col2_x, status_row1_y), wipe_text, font=content_font, fill=wipe_color)

    # 左列第二行：自动钓鱼状态
    auto_fishing = user_data.get('auto_fishing_enabled', False)
    if auto_fishing:
        auto_text = "自动钓鱼: 已开启"
        auto_color = success_color
    else:
        auto_text = "自动钓鱼: 已关闭"
        auto_color = error_color
    draw.text((status_col1_x, status_row2_y), auto_text, font=content_font, fill=auto_color)

    # 右列第二行：偷鱼CD信息
    steal_cd = user_data.get('steal_cooldown_remaining', 0)
    if steal_cd > 0:
        hours = steal_cd // 3600
        minutes = (steal_cd % 3600) // 60
        if hours > 0:
            cd_text = f"偷鱼冷却: {hours}小时{minutes}分钟"
        else:
            cd_text = f"偷鱼冷却: {minutes}分钟"
        cd_color = text_muted
    else:
        cd_text = "准备好偷鱼了！"
        cd_color = error_color
    draw.text((status_col2_x, status_row2_y), cd_text, font=content_font, fill=cd_color)

    # 第三行左列: 电鱼CD
    ef_cd = user_data.get('electric_fish_cooldown_remaining', 0)
    if ef_cd > 0:
        h, m = ef_cd // 3600, (ef_cd % 3600) // 60
        ef_cd_text = f"电鱼冷却: {h}小时{m}分钟" if h > 0 else f"电鱼冷却: {m}分钟"
        ef_cd_color = text_muted
    else: 
        ef_cd_text = "准备好电鱼了！"
        ef_cd_color = error_color
    draw.text((status_col1_x, status_row3_y), ef_cd_text, font=content_font, fill=ef_cd_color)

    # 第三行右列: 命运之轮
    wof_rem = user_data.get('wof_remaining_plays', 0)
    if wof_rem > 0:
        wof_text = f"命运之轮: 剩余 {wof_rem} 次"
        wof_color = error_color
    else:
        wof_text = "命运之轮: 已用完"
        wof_color = text_muted
    draw.text((status_col2_x, status_row3_y), wof_text, font=content_font, fill=wof_color)

    # 第四行：鱼塘信息
    pond_info = user_data.get('pond_info', {})
    if pond_info and pond_info.get('total_count', 0) > 0:
        # 左列：鱼塘鱼数
        pond_count_text = f"鱼塘数量: {pond_info['total_count']} 条， 价值: {pond_info['total_value']:,} 金币"
        draw.text((status_col1_x, status_row4_y), pond_count_text, font=content_font, fill=text_primary)
    else:
        # 鱼塘为空时显示
        pond_empty_text = "鱼塘里什么都没有..."
        draw.text((status_col1_x, status_row4_y), pond_empty_text, font=content_font, fill=text_muted)


    # 10. 底部信息 - 调整位置
    current_y += status_card_height + 15
    footer_text = f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    footer_w, footer_h = get_text_size(footer_text, small_font)
    footer_x = (width - footer_w) // 2
    draw.text((footer_x, current_y), footer_text, font=small_font, fill=text_secondary)

    # 12. 添加装饰性元素 - 保持简洁
    corner_size = 15  # 稍微减小装饰元素
    corner_color = COLOR_CORNER
    
    # 四角装饰
    draw.ellipse([8, 8, 8 + corner_size, 8 + corner_size], fill=corner_color)
    draw.ellipse([width - 8 - corner_size, 8, width - 8, 8 + corner_size], fill=corner_color)
    draw.ellipse([8, height - 8 - corner_size, 8 + corner_size, height - 8], fill=corner_color)
    draw.ellipse([width - 8 - corner_size, height - 8 - corner_size, width - 8, height - 8], fill=corner_color)

    return image


def get_user_state_data(user_repo, inventory_repo, item_template_repo, log_repo, buff_repo, game_config, user_id: str) -> Optional[Dict[str, Any]]:
    """
    获取用户状态数据
    
    Args:
        user_repo: 用户仓储
        inventory_repo: 库存仓储
        item_template_repo: 物品模板仓储
        log_repo: 日志仓储
        buff_repo: 用户增益仓储
        game_config: 游戏配置
        user_id: 用户ID
    
    Returns:
        包含用户状态信息的字典，如果用户不存在则返回None
    """
    from ..core.utils import get_now, get_today
    
    # 获取用户基本信息
    user = user_repo.get_by_id(user_id)
    if not user:
        return None
    
    # 获取当前装备的鱼竿
    current_rod = None
    rod_instance = inventory_repo.get_user_equipped_rod(user_id)
    if rod_instance:
        rod_template = item_template_repo.get_rod_by_id(rod_instance.rod_id)
        if rod_template:
            # 计算精炼后的最大耐久度，与背包一致：原始 * (1.5)^(精炼等级-1)
            if rod_template.durability is not None:
                refined_max_durability = int(rod_template.durability * (1.5 ** (max(rod_instance.refine_level, 1) - 1)))
            else:
                refined_max_durability = None

            # 如果实例是无限耐久，则上限也视为 None
            if rod_instance.current_durability is None:
                refined_max_durability = None

            current_rod = {
                'name': rod_template.name,
                'rarity': rod_template.rarity,
                'refine_level': rod_instance.refine_level,
                'current_durability': rod_instance.current_durability,
                'max_durability': refined_max_durability
            }
    
    # 获取当前装备的饰品
    current_accessory = None
    accessory_instance = inventory_repo.get_user_equipped_accessory(user_id)
    if accessory_instance:
        accessory_template = item_template_repo.get_accessory_by_id(accessory_instance.accessory_id)
        if accessory_template:
            current_accessory = {
                'name': accessory_template.name,
                'rarity': accessory_template.rarity,
                'refine_level': accessory_instance.refine_level
            }
    
    # 获取当前使用的鱼饵
    current_bait = None
    if user.current_bait_id:
        bait_template = item_template_repo.get_bait_by_id(user.current_bait_id)
        if bait_template:
            # 获取用户的鱼饵库存
            bait_inventory = inventory_repo.get_user_bait_inventory(user_id)
            bait_quantity = bait_inventory.get(user.current_bait_id, 0)
            current_bait = {
                'name': bait_template.name,
                'rarity': bait_template.rarity,
                'quantity': bait_quantity
            }
    
    # 获取钓鱼区域信息
    fishing_zone = None
    if user.fishing_zone_id:
        zone = inventory_repo.get_zone_by_id(user.fishing_zone_id)
        if zone:
            fishing_zone = {
                'name': zone.name,
                'description': zone.description,
                'rare_fish_quota': zone.daily_rare_fish_quota if hasattr(zone, 'daily_rare_fish_quota') else 0,
                'rare_fish_caught': zone.rare_fish_caught_today if hasattr(zone, 'rare_fish_caught_today') else 0
            }
    
    # 计算偷鱼剩余CD时间
    steal_cooldown_remaining = 0
    if user.last_steal_time:
        cooldown_seconds = game_config.get("steal", {}).get("cooldown_seconds", 14400)
        now = get_now()
        # 处理时区问题
        if user.last_steal_time.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        elif user.last_steal_time.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=user.last_steal_time.tzinfo)
        
        elapsed = (now - user.last_steal_time).total_seconds()
        if elapsed < cooldown_seconds:
            steal_cooldown_remaining = int(cooldown_seconds - elapsed)

    # 计算电鱼CD时间
    electric_fish_cooldown_remaining = 0
    if hasattr(user, 'last_electric_fish_time') and user.last_electric_fish_time:
        cooldown_seconds = game_config.get("electric_fish", {}).get("cooldown_seconds", 7200)
        now = get_now()
        if user.last_electric_fish_time.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        elif user.last_electric_fish_time.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=user.last_electric_fish_time.tzinfo)
        
        elapsed = (now - user.last_electric_fish_time).total_seconds()
        if elapsed < cooldown_seconds:
            electric_fish_cooldown_remaining = int(cooldown_seconds - elapsed)
    
    # 获取当前称号
    current_title = None
    if hasattr(user, 'current_title_id') and user.current_title_id:
        try:
            # 尝试从各种可能的来源获取称号信息
            title_info = None
            if hasattr(item_template_repo, 'get_title_by_id'):
                title_info = item_template_repo.get_title_by_id(user.current_title_id)
            
            if title_info:
                current_title = {
                    'id': user.current_title_id,
                    'name': title_info.name if hasattr(title_info, 'name') else str(title_info)
                }
            else:
                # 如果无法获取详细信息，至少显示称号ID
                current_title = {
                    'id': user.current_title_id,
                    'name': f"称号#{user.current_title_id}"
                }
        except:
            # 如果获取称号失败，忽略
            current_title = None
    
    # 获取总钓鱼次数
    total_fishing_count = getattr(user, 'total_fishing_count', 0)
    
    # 获取偷鱼总价值
    # steal_total_value = getattr(user, 'steal_total_value', 0)
    steal_total_value = '0' # 似乎没有偷鱼总价值字段？

    # 检查今日是否签到
    signed_in_today = False
    if hasattr(user, 'last_login_time') and user.last_login_time:
        today = get_now().date()
        last_login_date = user.last_login_time.date() if hasattr(user.last_login_time, 'date') else user.last_login_time
        signed_in_today = (last_login_date == today)
    
    # 计算擦弹剩余次数
    wipe_bomb_remaining = 0
    # 确保 user 对象有新添加的字段，做向后兼容
    if hasattr(user, 'last_wipe_bomb_date') and hasattr(user, 'wipe_bomb_attempts_today'):
        base_max_attempts = game_config.get("wipe_bomb", {}).get("max_attempts_per_day", 3)
        extra_attempts = 0
        boost_buff = buff_repo.get_active_by_user_and_type(user_id, "WIPE_BOMB_ATTEMPTS_BOOST")
        if boost_buff and boost_buff.payload:
            try:
                extra_attempts = json.loads(boost_buff.payload).get("amount", 0)
            except json.JSONDecodeError: pass
        
        total_max_attempts = base_max_attempts + extra_attempts
        
        today_str = get_today().strftime('%Y-%m-%d')
        used_attempts_today = 0
        # 如果记录的日期是今天，就使用记录的次数；否则次数为0
        if user.last_wipe_bomb_date == today_str:
            used_attempts_today = user.wipe_bomb_attempts_today

        wipe_bomb_remaining = max(0, total_max_attempts - used_attempts_today)
    else:
        # 如果数据库中的用户数据还没有新字段（例如，尚未迁移），提供一个默认值
        wipe_bomb_remaining = game_config.get("wipe_bomb", {}).get("max_attempts_per_day", 3)

    # 计算命运之轮剩余次数
    wheel_of_fate_daily_limit = game_config.get("wheel_of_fate_daily_limit", 3)
    wof_remaining_plays = 0
    if hasattr(user, 'last_wof_date') and hasattr(user, 'wof_plays_today'):
        today_str = get_today().strftime('%Y-%m-%d')
        if user.last_wof_date == today_str:
            wof_remaining_plays = max(0, wheel_of_fate_daily_limit - user.wof_plays_today)
        else:
            wof_remaining_plays = wheel_of_fate_daily_limit
    else:
        # 兼容旧数据，给予最大次数
        wof_remaining_plays = wheel_of_fate_daily_limit
    
    # 获取鱼塘信息
    pond_info = None
    try:
        # 使用与inventory_service.get_user_fish_pond相同的逻辑获取鱼塘信息
        inventory_items = inventory_repo.get_fish_inventory(user_id)
        total_value = inventory_repo.get_fish_inventory_value(user_id)
        
        # 计算总鱼数
        total_count = sum(item.quantity for item in inventory_items) if inventory_items else 0
        
        if total_count > 0 or total_value > 0:
            pond_info = {
                'total_count': total_count,
                'total_value': total_value
            }
        else:
            pond_info = {'total_count': 0, 'total_value': 0}
            
    except Exception as e:
        # 如果获取鱼塘信息失败，设置为默认值
        pond_info = {'total_count': 0, 'total_value': 0}
    
    return {
        'user_id': user.user_id,
        'nickname': user.nickname or user.user_id,
        'coins': user.coins,
        'premium_currency': getattr(user, 'premium_currency', 0),
        'current_rod': current_rod,
        'current_accessory': current_accessory,
        'current_bait': current_bait,
        'auto_fishing_enabled': user.auto_fishing_enabled,
        'steal_cooldown_remaining': steal_cooldown_remaining,
        'electric_fish_cooldown_remaining': electric_fish_cooldown_remaining,
        'fishing_zone': fishing_zone,
        'current_title': current_title,
        'total_fishing_count': total_fishing_count,
        'steal_total_value': steal_total_value,
        'signed_in_today': signed_in_today,
        'wipe_bomb_remaining': wipe_bomb_remaining,
        'pond_info': pond_info,
        'wof_remaining_plays': wof_remaining_plays,
    }