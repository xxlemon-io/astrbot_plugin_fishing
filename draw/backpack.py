import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .utils import get_user_avatar
from .styles import (
    IMG_WIDTH, PADDING, CORNER_RADIUS,
    COLOR_BACKGROUND, COLOR_HEADER_BG, COLOR_TEXT_WHITE, COLOR_TEXT_DARK,
    COLOR_TEXT_GRAY, COLOR_CARD_BG, COLOR_CARD_BORDER, COLOR_ACCENT,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_LOCK,
    COLOR_GOLD, COLOR_RARE, COLOR_REFINE_RED, COLOR_REFINE_ORANGE,
    COLOR_CORNER, load_font
)

def format_rarity_display(rarity: int) -> str:
    """格式化稀有度显示，支持显示到10星，10星以上显示为★★★★★★★★★★+"""
    if rarity <= 10:
        return '★' * rarity
    else:
        return '★★★★★★★★★★+'

def to_percentage(value: float) -> str:
    """将小数转换为百分比字符串"""
    if value is None:
        return "0%"
    if value < 1:
        return f"{value * 100:.2f}%"
    else:
        return f"{(value - 1) * 100:.2f}%"

def calculate_dynamic_height(user_data: Dict[str, Any]) -> int:
    """
    计算动态画布高度 - 使用保守估算
    
    Args:
        user_data: 用户背包数据
    
    Returns:
        计算出的画布高度
    """
    # 基础高度
    base_height = 200  # 标题 + 用户信息卡片 + 底部信息
    
    # 鱼竿区域高度 - 保守估算
    rods = user_data.get('rods', [])
    if rods:
        rows = (len(rods) + 1) // 2
        # 估算每个鱼竿卡片平均高度为200px（有描述的会更高）
        avg_height = 200
        rod_height = 35 + rows * avg_height + (rows - 1) * 15
    else:
        rod_height = 35 + 50
    
    # 饰品区域高度 - 保守估算
    accessories = user_data.get('accessories', [])
    if accessories:
        rows = (len(accessories) + 1) // 2
        # 估算每个饰品卡片平均高度为200px
        avg_height = 200
        accessory_height = 35 + rows * avg_height + (rows - 1) * 15
    else:
        accessory_height = 35 + 50
    
    # 鱼饵区域高度 - 保守估算
    baits = user_data.get('baits', [])
    if baits:
        rows = (len(baits) + 1) // 2
        # 估算每个鱼饵卡片平均高度为130px（较小）
        avg_height = 130
        bait_height = 35 + rows * avg_height + (rows - 1) * 15
    else:
        bait_height = 35 + 50
    
    # 道具区域高度 - 保守估算
    items = user_data.get('items', [])
    if items:
        rows = (len(items) + 1) // 2
        # 估算每个道具卡片平均高度为130px（较小）
        avg_height = 130
        item_height = 35 + rows * avg_height + (rows - 1) * 15
    else:
        item_height = 35 + 50
    
    # 区域间距
    section_spacing = 20 * 4  # 4个区域间距
    
    total_height = base_height + rod_height + accessory_height + bait_height + item_height + section_spacing
    return max(total_height, 600)  # 最小高度600

async def draw_backpack_image(user_data: Dict[str, Any], data_dir: str) -> Image.Image:
    """
    绘制用户背包图像
    
    Args:
        user_data: 包含用户背包信息的字典，包括：
            - user_id: 用户ID
            - nickname: 用户昵称
            - rods: 鱼竿列表
            - accessories: 饰品列表
            - baits: 鱼饵列表
            - items: 道具列表
            - is_truncated: 是否被截断
    
    Returns:
        PIL.Image.Image: 生成的背包图像
    """
    import asyncio
    
    # 计算物品总数
    total_items = (len(user_data.get('rods', [])) + 
                   len(user_data.get('accessories', [])) + 
                   len(user_data.get('baits', [])) + 
                   len(user_data.get('items', [])))
    
    # 如果物品数量过多，使用更短的超时时间
    timeout = 20.0 if total_items > 100 else 30.0
    
    try:
        return await asyncio.wait_for(_draw_backpack_image_impl(user_data, data_dir), timeout=timeout)
    except asyncio.TimeoutError:
        # 超时时返回简化版本
        return _create_fallback_image(user_data)


async def _draw_backpack_image_impl(user_data: Dict[str, Any], data_dir: str) -> Image.Image:
    """
    背包图片生成的实际实现
    """
    # 画布尺寸 - 使用动态高度
    width = 800
    # 先计算需要的高度
    height = calculate_dynamic_height(user_data)
    
    # 导入优化的渐变生成函数
    from .gradient_utils import create_vertical_gradient

    bg_top = (174, 214, 241)  # 柔和天蓝色
    bg_bot = (245, 251, 255)  # 温和淡蓝色
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)

    # 2. 加载字体
    title_font = load_font(32)
    subtitle_font = load_font(24)
    content_font = load_font(18)
    small_font = load_font(16)
    tiny_font = load_font(14)

    # 3. 颜色定义 - 使用统一颜色系统
    primary_dark = (52, 73, 94)      # 温和深蓝 - 主标题
    primary_medium = (74, 105, 134)  # 柔和中蓝 - 副标题
    primary_light = (108, 142, 191)  # 淡雅蓝 - 强调色
    
    # 文本色：和谐灰蓝色系
    text_primary = (55, 71, 79)      # 温和深灰 - 主要文本
    text_secondary = (120, 144, 156) # 柔和灰蓝 - 次要文本
    text_muted = (176, 190, 197)     # 温和浅灰 - 弱化文本
    
    # 状态色：使用统一颜色
    success_color = COLOR_SUCCESS
    warning_color = COLOR_WARNING
    error_color = COLOR_ERROR
    lock_color = COLOR_LOCK
    
    # 背景色：更柔和的对比
    card_bg = (255, 255, 255, 240)   # 高透明度白色
    
    # 特殊色：使用统一颜色
    gold_color = COLOR_GOLD
    rare_color = COLOR_RARE

    # 导入优化的文本处理函数
    from .text_utils import get_text_size_cached, wrap_text_by_width_optimized, create_text_cache
    
    # 创建文本测量缓存
    text_cache = create_text_cache()
    
    # 4. 获取文本尺寸的辅助函数（使用缓存）
    def get_text_size(text, font):
        return get_text_size_cached(text, font, text_cache)
    
    # 文本按像素宽度换行，确保不超出卡片（使用优化版本）
    def wrap_text_by_width(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
        return wrap_text_by_width_optimized(text, font, max_width, text_cache)

    # 动态扩展画布高度，避免被裁剪
    def ensure_height(needed_height: int):
        nonlocal image, draw, height
        if needed_height <= height:
            return
        new_h = needed_height
        new_image = Image.new('RGB', (width, new_h), (255, 255, 255))
        bg = create_vertical_gradient(width, new_h, bg_top, bg_bot)
        new_image.paste(bg, (0, 0))
        new_image.paste(image, (0, 0))
        image = new_image
        draw = ImageDraw.Draw(image)
        height = new_h

    # 计算不同类型卡片的动态高度
    def measure_rod_card_height(rod, card_width: int) -> int:
        line_h = get_text_size("测", tiny_font)[1] + 2
        attr_lines = 0
        if rod.get('bonus_fish_quality_modifier', 1.0) not in (1.0, 1) and rod.get('bonus_fish_quality_modifier', 0) > 0:
            attr_lines += 1
        if rod.get('bonus_fish_quantity_modifier', 1.0) not in (1.0, 1) and rod.get('bonus_fish_quantity_modifier', 0) > 0:
            attr_lines += 1
        if rod.get('bonus_rare_fish_chance', 1.0) not in (1.0, 1) and rod.get('bonus_rare_fish_chance', 0) > 0:
            attr_lines += 1
        desc_lines = 0
        if rod.get('description'):
            lines = wrap_text_by_width(f"{rod['description']}", tiny_font, card_width - 30)
            desc_lines = len(lines)
        
        # 检查是否有耐久度信息，如果有则增加高度
        durability_height = 0
        if rod.get('max_durability') is not None or rod.get('current_durability') is None:
            durability_height = 20  # 耐久度显示的额外高度（包括无限耐久）
        
        header_height = 85 + durability_height
        bottom_pad = 20
        card_h = header_height + attr_lines * 18 + desc_lines * line_h + bottom_pad
        return max(card_h, 160)

    def measure_accessory_card_height(acc, card_width: int) -> int:
        line_h = get_text_size("测", tiny_font)[1] + 2
        attr_lines = 0
        if acc.get('bonus_fish_quality_modifier', 1.0) not in (1.0, 1) and acc.get('bonus_fish_quality_modifier', 0) > 0:
            attr_lines += 1
        if acc.get('bonus_fish_quantity_modifier', 1.0) not in (1.0, 1) and acc.get('bonus_fish_quantity_modifier', 0) > 0:
            attr_lines += 1
        if acc.get('bonus_rare_fish_chance', 1.0) not in (1.0, 1) and acc.get('bonus_rare_fish_chance', 0) > 0:
            attr_lines += 1
        if acc.get('bonus_coin_modifier', 1.0) not in (1.0, 1) and acc.get('bonus_coin_modifier', 0) > 0:
            attr_lines += 1
        desc_lines = 0
        if acc.get('description'):
            lines = wrap_text_by_width(f"{acc['description']}", tiny_font, card_width - 30)
            desc_lines = len(lines)
        
        header_height = 85
        bottom_pad = 20
        card_h = header_height + attr_lines * 18 + desc_lines * line_h + bottom_pad
        return max(card_h, 160)

    def measure_bait_card_height(bait, card_width: int) -> int:
        line_h = get_text_size("测", tiny_font)[1] + 2
        desc_lines = 0
        if bait.get('effect_description'):
            lines = wrap_text_by_width(f"效果: {bait['effect_description']}", tiny_font, card_width - 30)
            desc_lines = len(lines)
        
        # 基础信息高度：名称+星级+数量 = 70px
        header_height = 70 + (20 if bait.get('duration_minutes', 0) > 0 else 0)
        
        # 动态底部间距：有描述时稍大，无描述时紧凑
        bottom_pad = 15 if desc_lines > 0 else 10
        card_h = header_height + desc_lines * line_h + bottom_pad
        
        # 如果没有持续时间也没有效果描述，使用紧凑高度
        if bait.get('duration_minutes', 0) <= 0 and not bait.get('effect_description'):
            return 95  # 紧凑高度：70 + 25 = 95px
        
        # 移除最小高度限制，让卡片根据实际内容调整
        return card_h

    def measure_item_card_height(item, card_width: int) -> int:
        line_h = get_text_size("测", tiny_font)[1] + 2
        desc_lines = 0
        if item.get('effect_description'):
            lines = wrap_text_by_width(f"效果: {item['effect_description']}", tiny_font, card_width - 30)
            desc_lines = len(lines)
        header_height = 70
        bottom_pad = 15 if desc_lines > 0 else 10
        return header_height + desc_lines * line_h + bottom_pad

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
    title_text = "用户背包"
    title_w, title_h = get_text_size(title_text, title_font)
    title_x = (width - title_w) // 2
    title_y = 20
    draw.text((title_x, title_y), title_text, font=title_font, fill=primary_dark)

    # 用户信息卡片
    current_y = title_y + title_h + 15
    card_height = 80
    card_margin = 15
    # 保持与装备卡片一致的边距（30px左右边距，与装备区域对齐）
    user_card_margin = 30
    
    # 用户信息卡片
    draw_rounded_rectangle(draw, 
                         (user_card_margin, current_y, width - user_card_margin, current_y + card_height), 
                         10, fill=card_bg)
    
    # 列位置
    col1_x_without_avatar = user_card_margin + 20  # 第一列（使用新的边距）
    avatar_size = 60
    col1_x_with_avatar = col1_x_without_avatar + avatar_size + 20  # 有头像时偏移
    col1_x = col1_x_without_avatar # 默认无头像
    col2_x = col1_x + 300 # 第二列位置（初始，若头像改变后会重算）
    
    # 行位置
    row1_y = current_y + 12
    row2_y = current_y + 52

    # 绘制用户头像 - 如有
    if user_id := user_data.get('user_id'):
        if avatar_image := await get_user_avatar(user_id, data_dir, avatar_size):
            image.paste(avatar_image, (col1_x, row1_y), avatar_image)
            col1_x = col1_x_with_avatar # 更新 col1_x 以适应头像位置
            col2_x = col1_x + 300  # 头像存在时，第二列起点随之右移

    # 用户昵称
    nickname = user_data.get('nickname', '未知用户')
    nickname_text = f"{nickname}"
    draw.text((col1_x, row1_y), nickname_text, font=subtitle_font, fill=primary_medium)
    
    # 统计信息 + 装备总价值（用户名下方横向排布）
    # 使用实际总数而非显示数量
    rods_count = user_data.get('total_rods', len(user_data.get('rods', [])))
    accessories_count = user_data.get('total_accessories', len(user_data.get('accessories', [])))
    baits_count = user_data.get('total_baits', len(user_data.get('baits', [])))
    items_count = user_data.get('total_items', len(user_data.get('items', [])))
    
    # 计算总价值（基于显示的物品）
    total_value = 0
    for rod in user_data.get('rods', []):
        rarity = rod.get('rarity', 1)
        refine_level = rod.get('refine_level', 1)
        base_value = rarity * 1000
        refined_value = base_value * (1 + max(refine_level - 1, 0) * 0.5)
        total_value += refined_value
    for accessory in user_data.get('accessories', []):
        rarity = accessory.get('rarity', 1)
        refine_level = accessory.get('refine_level', 1)
        base_value = rarity * 1000
        refined_value = base_value * (1 + max(refine_level - 1, 0) * 0.5)
        total_value += refined_value
    for bait in user_data.get('baits', []):
        rarity = bait.get('rarity', 1)
        quantity = bait.get('quantity', 0)
        base_value = rarity * 100
        total_value += base_value * quantity
    for item in user_data.get('items', []):
        rarity = item.get('rarity', 1)
        quantity = item.get('quantity', 0)
        base_value = rarity * 100
        total_value += base_value * quantity
    
    stats_text = f"鱼竿: {rods_count} | 饰品: {accessories_count} | 鱼饵: {baits_count} | 道具: {items_count}"
    value_text = f"装备总价值: {int(total_value):,} 金币"
    stats_w, stats_h = get_text_size(stats_text, small_font)
    value_w, value_h = get_text_size(value_text, small_font)
    gap = 24
    row_y = row2_y - 6
    available_w = (width - card_margin - 10) - col1_x
    if stats_w + gap + value_w <= available_w:
        draw.text((col1_x, row_y), stats_text, font=small_font, fill=text_secondary)
        draw.text((col1_x + stats_w + gap, row_y), value_text, font=small_font, fill=gold_color)
    else:
        draw.text((col1_x, row_y), stats_text, font=small_font, fill=text_secondary)
        draw.text((col1_x, row_y + stats_h + 4), value_text, font=small_font, fill=gold_color)

    current_y += card_height + 20

    # 鱼竿区域
    rods = user_data.get('rods', [])
    rod_section_y = current_y
    draw.text((30, rod_section_y), "鱼竿", font=subtitle_font, fill=primary_medium)
    current_y += 35

    if rods:
        # 计算鱼竿卡片布局 - 每行2个（动态高度）
        card_width = (width - 90) // 2
        card_margin = 15
        # 行起始与下一行起点
        row_start_y = current_y
        next_row_start_y = current_y
        
        for i, rod in enumerate(rods):
            row = i // 2
            col = i % 2
            x = 30 + col * (card_width + card_margin)
            
            if col == 0:
                # 开启新行：将起始Y推进到上一行计算出的下一行起点
                row_start_y = next_row_start_y
                # 预先量测本行行高（左右取最大）
                left_h = measure_rod_card_height(rod, card_width)
                right_index = i + 1
                if right_index < len(rods):
                    right_h = measure_rod_card_height(rods[right_index], card_width)
                else:
                    right_h = 0
                row_h = max(left_h, right_h)
                y = row_start_y
                next_row_start_y = row_start_y + row_h + card_margin
                # 使用统一行高
                card_height = row_h
            else:
                # 同一行右列与左列对齐
                y = row_start_y
                # 右列使用相同行高
                card_height = row_h
            ensure_height(y + card_height + 40)

            # 绘制鱼竿卡片
            draw_rounded_rectangle(draw, 
                                 (x, y, x + card_width, y + card_height), 
                                 8, fill=card_bg)
            
            # 鱼竿名称和ID在同一行
            rod_name = rod['name'][:15] + "..." if len(rod['name']) > 15 else rod['name']
            display_code = rod.get('display_code', f"ID{rod.get('instance_id', 'N/A')}")
            
            # 计算名称宽度，然后在其右边放置ID
            name_w, _ = get_text_size(rod_name, content_font)
            draw.text((x + 15, y + 15), rod_name, font=content_font, fill=text_primary)
            id_w, id_h = get_text_size("ID: 000000", tiny_font)
            # 让ID与装备名底部对齐（y同基线高度）
            draw.text((x + 15 + name_w + 10, y + 15 + (get_text_size(rod_name, content_font)[1] - id_h)), f"ID: {display_code}", font=tiny_font, fill=primary_light)
            
            # 锁定状态标识（右上角，参考道具消耗品位置）
            is_locked = rod.get('is_locked', False)
            if is_locked:
                label_text = "🔒 锁定保护中"
                lw, lh = get_text_size(label_text, tiny_font)
                draw.text((x + card_width - 15 - lw, y + 12), label_text, font=tiny_font, fill=lock_color)
            
            # 稀有度和精炼等级
            rarity = rod.get('rarity', 1)
            refine_level = rod.get('refine_level', 1)
            if refine_level >= 10:
                star_color = COLOR_REFINE_RED  # 红色 - 10级
            elif refine_level >= 6:
                star_color = COLOR_REFINE_ORANGE  # 橙色 - 6-9级
            elif rarity > 4 and refine_level > 4:
                star_color = rare_color
            elif rarity > 3:
                star_color = warning_color
            else:
                star_color = text_secondary
            draw.text((x + 15, y + 40), f"{format_rarity_display(rarity)} Lv.{refine_level}", font=small_font, fill=star_color)
            
            # 装备状态和耐久度
            is_equipped = rod.get('is_equipped', False)
            current_dur = rod.get('current_durability')
            max_dur = rod.get('max_durability')
            
            if is_equipped:
                draw.text((x + 15, y + 60), "已装备", font=small_font, fill=success_color)
            else:
                draw.text((x + 15, y + 60), "未装备", font=small_font, fill=text_muted)
            
            # 显示耐久度
            if max_dur is not None and current_dur is not None:
                # 有限耐久装备
                durability_text = f"耐久: {current_dur}/{max_dur}"
                # 根据耐久度设置颜色 - 使用与整体设计一致的颜色系统
                durability_ratio = current_dur / max_dur if max_dur > 0 else 0
                if durability_ratio > 0.6:
                    dur_color = success_color  # 使用成功色 - 温和绿
                elif durability_ratio > 0.3:
                    dur_color = warning_color  # 使用警告色 - 柔和橙
                else:
                    dur_color = error_color    # 使用错误色 - 温和红
                draw.text((x + 15, y + 80), durability_text, font=tiny_font, fill=dur_color)
                bonus_y = y + 105  # 调整后续内容位置
            elif current_dur is None:
                # 无限耐久装备
                durability_text = "耐久: ∞"
                dur_color = primary_light     # 使用主色调 - 淡雅蓝，与UI风格一致
                draw.text((x + 15, y + 80), durability_text, font=tiny_font, fill=dur_color)
                bonus_y = y + 105  # 调整后续内容位置
            else:
                bonus_y = y + 85
            
            # 属性加成 - 参考format_accessory_or_rod函数
            if rod.get('bonus_fish_quality_modifier', 1.0) != 1.0 and rod.get('bonus_fish_quality_modifier', 1) != 1 and rod.get('bonus_fish_quality_modifier', 1) > 0:
                bonus_text = f"鱼类品质加成: {to_percentage(rod['bonus_fish_quality_modifier'])}"
                draw.text((x + 15, bonus_y), bonus_text, font=tiny_font, fill=primary_light)
                bonus_y += 18
            if rod.get('bonus_fish_quantity_modifier', 1.0) != 1.0 and rod.get('bonus_fish_quantity_modifier', 1) != 1 and rod.get('bonus_fish_quantity_modifier', 1) > 0:
                bonus_text = f"鱼类数量加成: {to_percentage(rod['bonus_fish_quantity_modifier'])}"
                draw.text((x + 15, bonus_y), bonus_text, font=tiny_font, fill=primary_light)
                bonus_y += 18
            if rod.get('bonus_rare_fish_chance', 1.0) != 1.0 and rod.get('bonus_rare_fish_chance', 1) != 1 and rod.get('bonus_rare_fish_chance', 1) > 0:
                bonus_text = f"钓鱼几率加成: {to_percentage(rod['bonus_rare_fish_chance'])}"
                draw.text((x + 15, bonus_y), bonus_text, font=tiny_font, fill=primary_light)
                bonus_y += 18
            
            # 描述 - 支持换行且不超出卡片
            if rod.get('description'):
                desc_text = f"{rod['description']}"
                available_width = card_width - 30
                lines = wrap_text_by_width(desc_text, tiny_font, available_width)
                # 计算可绘制的最大行数，避免超出卡片底部
                line_h = get_text_size("测", tiny_font)[1] + 2
                max_lines = max((y + card_height - 20) - bonus_y, 0) // line_h
                if max_lines > 0:
                    for i, line in enumerate(lines[:max_lines]):
                        draw.text((x + 15, bonus_y + i * line_h), line, font=tiny_font, fill=text_secondary)
        
        # 更新当前Y位置到下一行起点
        current_y = next_row_start_y
    else:
        draw.text((30, current_y), "🎣 您还没有鱼竿，快去商店购买或抽奖获得吧！", font=content_font, fill=text_muted)
        current_y += 50

    current_y += 20

    # 饰品区域
    accessories = user_data.get('accessories', [])
    draw.text((30, current_y), "饰品", font=subtitle_font, fill=primary_medium)
    current_y += 35

    if accessories:
        # 计算饰品卡片布局 - 每行2个（动态高度）
        card_width = (width - 90) // 2
        card_margin = 15
        row_start_y = current_y
        next_row_start_y = current_y
        
        for i, accessory in enumerate(accessories):
            row = i // 2
            col = i % 2
            x = 30 + col * (card_width + card_margin)
            
            if col == 0:
                row_start_y = next_row_start_y
                left_h = measure_accessory_card_height(accessory, card_width)
                right_index = i + 1
                if right_index < len(accessories):
                    right_h = measure_accessory_card_height(accessories[right_index], card_width)
                else:
                    right_h = 0
                row_h = max(left_h, right_h)
                y = row_start_y
                next_row_start_y = row_start_y + row_h + card_margin
                # 使用统一行高
                card_height = row_h
            else:
                y = row_start_y
                # 右列使用相同行高
                card_height = row_h
            ensure_height(y + card_height + 40)

            # 绘制饰品卡片
            draw_rounded_rectangle(draw, 
                                 (x, y, x + card_width, y + card_height), 
                                 8, fill=card_bg)
            
            # 饰品名称和ID在同一行
            acc_name = accessory['name'][:15] + "..." if len(accessory['name']) > 15 else accessory['name']
            display_code = accessory.get('display_code', f"ID{accessory.get('instance_id', 'N/A')}")
            
            # 计算名称宽度，然后在其右边放置ID
            name_w, _ = get_text_size(acc_name, content_font)
            draw.text((x + 15, y + 15), acc_name, font=content_font, fill=text_primary)
            id_w, id_h = get_text_size("ID: 000000", tiny_font)
            draw.text((x + 15 + name_w + 10, y + 15 + (get_text_size(acc_name, content_font)[1] - id_h)), f"ID: {display_code}", font=tiny_font, fill=primary_light)
            
            # 锁定状态标识（右上角，参考道具消耗品位置）
            is_locked = accessory.get('is_locked', False)
            if is_locked:
                label_text = "🔒 锁定"
                lw, lh = get_text_size(label_text, tiny_font)
                draw.text((x + card_width - 15 - lw, y + 12), label_text, font=tiny_font, fill=lock_color)
            
            # 稀有度和精炼等级
            rarity = accessory.get('rarity', 1)
            refine_level = accessory.get('refine_level', 1)
            if refine_level >= 10:
                star_color = COLOR_REFINE_RED  # 红色 - 10级
            elif refine_level >= 6:
                star_color = COLOR_REFINE_ORANGE  # 橙色 - 6-9级
            elif rarity > 4 and refine_level > 4:
                star_color = rare_color
            elif rarity > 3:
                star_color = warning_color
            else:
                star_color = text_secondary
            draw.text((x + 15, y + 40), f"{format_rarity_display(rarity)} Lv.{refine_level}", font=small_font, fill=star_color)
            
            # 装备状态
            is_equipped = accessory.get('is_equipped', False)
            if is_equipped:
                draw.text((x + 15, y + 60), "已装备", font=small_font, fill=success_color)
            else:
                draw.text((x + 15, y + 60), "未装备", font=small_font, fill=text_muted)
            
            # 属性加成 - 参考format_accessory_or_rod函数
            bonus_y = y + 85
            if accessory.get('bonus_fish_quality_modifier', 1.0) != 1.0 and accessory.get('bonus_fish_quality_modifier', 1) != 1 and accessory.get('bonus_fish_quality_modifier', 1) > 0:
                bonus_text = f"鱼类品质加成: {to_percentage(accessory['bonus_fish_quality_modifier'])}"
                draw.text((x + 15, bonus_y), bonus_text, font=tiny_font, fill=primary_light)
                bonus_y += 18
            if accessory.get('bonus_fish_quantity_modifier', 1.0) != 1.0 and accessory.get('bonus_fish_quantity_modifier', 1) != 1 and accessory.get('bonus_fish_quantity_modifier', 1) > 0:
                bonus_text = f"鱼类数量加成: {to_percentage(accessory['bonus_fish_quantity_modifier'])}"
                draw.text((x + 15, bonus_y), bonus_text, font=tiny_font, fill=primary_light)
                bonus_y += 18
            if accessory.get('bonus_rare_fish_chance', 1.0) != 1.0 and accessory.get('bonus_rare_fish_chance', 1) != 1 and accessory.get('bonus_rare_fish_chance', 1) > 0:
                bonus_text = f"钓鱼几率加成: {to_percentage(accessory['bonus_rare_fish_chance'])}"
                draw.text((x + 15, bonus_y), bonus_text, font=tiny_font, fill=primary_light)
                bonus_y += 18
            if accessory.get('bonus_coin_modifier', 1.0) != 1.0 and accessory.get('bonus_coin_modifier', 1) != 1 and accessory.get('bonus_coin_modifier', 1) > 0:
                bonus_text = f"金币加成: {to_percentage(accessory['bonus_coin_modifier'])}"
                draw.text((x + 15, bonus_y), bonus_text, font=tiny_font, fill=gold_color)
                bonus_y += 18
            
            # 描述 - 支持换行且不超出卡片
            if accessory.get('description'):
                desc_text = f"{accessory['description']}"
                available_width = card_width - 30
                lines = wrap_text_by_width(desc_text, tiny_font, available_width)
                line_h = get_text_size("测", tiny_font)[1] + 2
                max_lines = max((y + card_height - 20) - bonus_y, 0) // line_h
                if max_lines > 0:
                    for i, line in enumerate(lines[:max_lines]):
                        draw.text((x + 15, bonus_y + i * line_h), line, font=tiny_font, fill=text_secondary)
        
        # 更新当前Y位置
        current_y = next_row_start_y
    else:
        draw.text((30, current_y), "💍 您还没有饰品，快去商店购买或抽奖获得吧！", font=content_font, fill=text_muted)
        current_y += 50

    current_y += 20

    # 鱼饵区域
    baits = user_data.get('baits', [])
    draw.text((30, current_y), "鱼饵", font=subtitle_font, fill=primary_medium)
    current_y += 35

    if baits:
        # 计算鱼饵卡片布局 - 每行2个（动态高度）
        card_width = (width - 90) // 2
        card_margin = 15
        row_start_y = current_y
        next_row_start_y = current_y
        
        for i, bait in enumerate(baits):
            row = i // 2
            col = i % 2
            x = 30 + col * (card_width + card_margin)
            
            if col == 0:
                row_start_y = next_row_start_y
                left_h = measure_bait_card_height(bait, card_width)
                right_index = i + 1
                if right_index < len(baits):
                    right_h = measure_bait_card_height(baits[right_index], card_width)
                else:
                    right_h = 0
                row_h = max(left_h, right_h)
                y = row_start_y
                next_row_start_y = row_start_y + row_h + card_margin
                # 使用统一行高绘制，确保同一行卡片高度一致
                card_height = row_h
            else:
                y = row_start_y
                # 右列也使用相同的行高
                card_height = row_h
            ensure_height(y + card_height + 40)

            # 绘制鱼饵卡片
            draw_rounded_rectangle(draw, 
                                 (x, y, x + card_width, y + card_height), 
                                 6, fill=card_bg)
            
            # 鱼饵名称 和 短码
            bait_name = bait['name'][:12] + "..." if len(bait['name']) > 12 else bait['name']
            name_w, _ = get_text_size(bait_name, small_font)
            draw.text((x + 15, y + 10), bait_name, font=small_font, fill=text_primary)
            
            # 生成B前缀短码（简单数字ID）
            bait_id = int(bait.get('bait_id', 0) or 0)
            bcode = f"B{bait_id}" if bait_id else "B0"
            draw.text((x + 15 + name_w + 10, y + 12), f"ID: {bcode}", font=tiny_font, fill=primary_light)
            
            # 稀有度
            rarity = bait.get('rarity', 1)
            star_color = rare_color if rarity > 4 else warning_color if rarity >= 3 else text_secondary
            draw.text((x + 15, y + 30), format_rarity_display(rarity), font=tiny_font, fill=star_color)
            
            # 数量
            quantity = bait.get('quantity', 0)
            draw.text((x + 15, y + 50), f"数量: {quantity}", font=tiny_font, fill=text_secondary)
            
            # 持续时间（动态排布，存在才占位）
            next_y = y + 70
            duration = bait.get('duration_minutes', 0)
            if duration > 0:
                draw.text((x + 15, next_y), f"持续: {duration}分钟", font=tiny_font, fill=primary_light)
                next_y += 20
            
            # 效果描述
            if bait.get('effect_description'):
                effect_text = f"效果: {bait['effect_description']}"
                available_width = card_width - 30
                lines = wrap_text_by_width(effect_text, tiny_font, available_width)
                line_h = get_text_size("测", tiny_font)[1] + 2
                max_lines = max((y + card_height - 15) - next_y, 0) // line_h
                if max_lines > 0:
                    for i, line in enumerate(lines[:max_lines]):
                        draw.text((x + 15, next_y + i * line_h), line, font=tiny_font, fill=text_secondary)
            
            # 底部保留空间（不再在左下角重复ID）
        
        # 更新当前Y位置
        current_y = next_row_start_y
    else:
        draw.text((30, current_y), "🐟 您还没有鱼饵，快去商店购买或抽奖获得吧！", font=content_font, fill=text_muted)
        current_y += 50

    current_y += 20

    # 道具区域
    items = user_data.get('items', [])
    draw.text((30, current_y), "道具", font=subtitle_font, fill=primary_medium)
    current_y += 35

    if items:
        # 计算道具卡片布局 - 每行2个（动态高度）
        card_width = (width - 90) // 2
        card_margin = 15
        row_start_y = current_y
        next_row_start_y = current_y

        for i, item in enumerate(items):
            row = i // 2
            col = i % 2
            x = 30 + col * (card_width + card_margin)

            if col == 0:
                row_start_y = next_row_start_y
                
                # Pre-measure card heights for the current row
                left_h = measure_item_card_height(item, card_width)
                right_index = i + 1
                if right_index < len(items):
                    right_h = measure_item_card_height(items[right_index], card_width)
                else:
                    right_h = 0
                
                row_h = max(left_h, right_h)
                y = row_start_y
                next_row_start_y = row_start_y + row_h + card_margin
                card_height = row_h
            else:
                y = row_start_y
                card_height = row_h
            ensure_height(y + card_height + 40)

            draw_rounded_rectangle(draw, (x, y, x + card_width, y + card_height), 6, fill=card_bg)

            item_name = item['name'][:12] + "..." if len(item['name']) > 12 else item['name']
            name_w, _ = get_text_size(item_name, small_font)
            draw.text((x + 15, y + 10), item_name, font=small_font, fill=text_primary)
            # 显示 D 前缀短码（简单数字ID）
            item_id = int(item.get('item_id', 0) or 0)
            dcode = f"D{item_id}" if item_id else "D0"
            draw.text((x + 15 + name_w + 10, y + 12), f"ID: {dcode}", font=tiny_font, fill=primary_light)
            # 消耗品标识（右上角）
            label_text = "消耗" if item.get('is_consumable') else "非消耗"
            lw, lh = get_text_size(label_text, tiny_font)
            draw.text((x + card_width - 15 - lw, y + 12), label_text, font=tiny_font, fill=success_color if item.get('is_consumable') else text_muted)

            rarity = item.get('rarity', 1)
            star_color = rare_color if rarity > 4 else warning_color if rarity >= 3 else text_secondary
            draw.text((x + 15, y + 30), format_rarity_display(rarity), font=tiny_font, fill=star_color)

            quantity = item.get('quantity', 0)
            draw.text((x + 15, y + 50), f"数量: {quantity}", font=tiny_font, fill=text_secondary)

            next_y = y + 70
            if effect_desc := item.get('effect_description'):
                available_width = card_width - 30
                lines = wrap_text_by_width(f"效果: {effect_desc}", tiny_font, available_width)
                line_h = get_text_size("测", tiny_font)[1] + 2
                max_lines = max((y + card_height - 15) - next_y, 0) // line_h
                if max_lines > 0:
                    for line_idx, line in enumerate(lines[:max_lines]):
                        draw.text((x + 15, next_y + line_idx * line_h), line, font=tiny_font, fill=text_secondary)
        current_y = next_row_start_y
    else:
        draw.text((30, current_y), "📦 您还没有道具。", font=content_font, fill=text_muted)
        current_y += 50

    current_y += 20

    # 6. 底部信息 - 显示生成时间和截断提示
    ensure_height(height - 10)
    
    # 如果内容被截断或过滤，显示提示信息
    if user_data.get('is_truncated', False):
        filter_parts = []
        if user_data.get('rods_filtered', False):
            filter_parts.append(f"鱼竿:仅显示5星以上({user_data.get('displayed_rods', 0)}/{user_data.get('total_rods', 0)})")
        if user_data.get('accessories_filtered', False):
            filter_parts.append(f"饰品:仅显示5星以上({user_data.get('displayed_accessories', 0)}/{user_data.get('total_accessories', 0)})")
        
        if filter_parts:
            warning_text = f"⚠️ 物品过多已智能过滤 | {' | '.join(filter_parts)}"
        else:
            warning_text = "⚠️ 物品过多，仅显示部分内容！"
        
        warning_text += " | 建议及时清理背包"
        warning_w, warning_h = get_text_size(warning_text, small_font)
        warning_x = (width - warning_w) // 2
        draw.text((warning_x, current_y), warning_text, font=small_font, fill=warning_color)
        current_y += warning_h + 10
    
    footer_text = f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    footer_w, footer_h = get_text_size(footer_text, small_font)
    footer_x = (width - footer_w) // 2
    # 如果超出原始高度，则扩展画布
    needed_height = current_y + footer_h + 30
    if needed_height > height:
        # 扩展画布高度
        new_image = Image.new('RGB', (width, needed_height), (255, 255, 255))
        # 重新绘制渐变背景
        bg = create_vertical_gradient(width, needed_height, bg_top, bg_bot)
        new_image.paste(bg, (0, 0))
        new_image.paste(image, (0, 0))
        image = new_image
        draw = ImageDraw.Draw(image)
        height = needed_height
    draw.text((footer_x, current_y), footer_text, font=small_font, fill=text_secondary)

    # 添加装饰性元素
    corner_size = 15
    corner_color = COLOR_CORNER
    
    # 四角装饰
    draw.ellipse([8, 8, 8 + corner_size, 8 + corner_size], fill=corner_color)
    draw.ellipse([width - 8 - corner_size, 8, width - 8, 8 + corner_size], fill=corner_color)
    draw.ellipse([8, height - 8 - corner_size, 8 + corner_size, height - 8], fill=corner_color)
    draw.ellipse([width - 8 - corner_size, height - 8 - corner_size, width - 8, height - 8], fill=corner_color)

    return image


def get_user_backpack_data(inventory_service, user_id: str, max_items_per_category: int = 50) -> Dict[str, Any]:
    """
    获取用户背包数据（带智能过滤）
    
    当装备数量过多时，自动过滤只显示5星以上装备，以提升性能和可读性
    
    Args:
        inventory_service: 库存服务
        user_id: 用户ID
        max_items_per_category: 每个分类最多显示的物品数量（默认50）
    
    Returns:
        包含用户背包信息的字典
    """
    # 获取鱼竿库存
    rod_result = inventory_service.get_user_rod_inventory(user_id)
    all_rods = rod_result.get('rods', []) if rod_result.get('success') else []
    
    # 获取饰品库存
    accessory_result = inventory_service.get_user_accessory_inventory(user_id)
    all_accessories = accessory_result.get('accessories', []) if accessory_result.get('success') else []
    
    # 获取鱼饵库存
    bait_result = inventory_service.get_user_bait_inventory(user_id)
    all_baits = bait_result.get('baits', []) if bait_result.get('success') else []
    
    # 获取道具库存
    item_result = inventory_service.get_user_item_inventory(user_id)
    all_items = item_result.get('items', []) if item_result.get('success') else []
    
    # 智能过滤：装备过多时只显示5星以上
    filtered_rods = all_rods
    filtered_accessories = all_accessories
    rods_filtered = False
    accessories_filtered = False
    
    # 鱼竿过多时过滤
    if len(all_rods) > 30:
        high_rarity_rods = [r for r in all_rods if r.get('rarity', 1) >= 5]
        if len(high_rarity_rods) > 0:
            # 即使5星以上也限制最多100项
            filtered_rods = high_rarity_rods[:min(100, max_items_per_category)]
            rods_filtered = True
        else:
            # 如果没有5星以上，按稀有度排序取前N个
            filtered_rods = sorted(all_rods, key=lambda x: x.get('rarity', 1), reverse=True)[:max_items_per_category]
            rods_filtered = True
    else:
        filtered_rods = all_rods[:max_items_per_category]
    
    # 饰品过多时过滤
    if len(all_accessories) > 30:
        high_rarity_accessories = [a for a in all_accessories if a.get('rarity', 1) >= 5]
        if len(high_rarity_accessories) > 0:
            # 即使5星以上也限制最多100项
            filtered_accessories = high_rarity_accessories[:min(100, max_items_per_category)]
            accessories_filtered = True
        else:
            # 如果没有5星以上，按稀有度排序取前N个
            filtered_accessories = sorted(all_accessories, key=lambda x: x.get('rarity', 1), reverse=True)[:max_items_per_category]
            accessories_filtered = True
    else:
        filtered_accessories = all_accessories[:max_items_per_category]
    
    # 鱼饵和道具仍使用数量限制
    filtered_baits = all_baits[:max_items_per_category]
    filtered_items = all_items[:max_items_per_category]
    
    # 判断是否被截断或过滤
    is_truncated = (len(all_rods) > len(filtered_rods) or 
                   len(all_accessories) > len(filtered_accessories) or
                   len(all_baits) > len(filtered_baits) or
                   len(all_items) > len(filtered_items))
    
    return {
        'user_id': user_id,
        'nickname': user_id,
        'rods': filtered_rods,
        'accessories': filtered_accessories,
        'baits': filtered_baits,
        'items': filtered_items,
        'total_rods': len(all_rods),
        'total_accessories': len(all_accessories),
        'total_baits': len(all_baits),
        'total_items': len(all_items),
        'displayed_rods': len(filtered_rods),
        'displayed_accessories': len(filtered_accessories),
        'is_truncated': is_truncated,
        'rods_filtered': rods_filtered,
        'accessories_filtered': accessories_filtered
    }


def _create_fallback_image(user_data: Dict[str, Any]) -> Image.Image:
    """
    创建简化的回退图像，当主生成过程超时时使用
    """
    from datetime import datetime
    
    # 创建简单的白色背景
    width, height = 800, 600
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = load_font(32)
    content_font = load_font(18)
    small_font = load_font(16)
    
    # 颜色定义
    primary_dark = (52, 73, 94)
    text_secondary = (120, 144, 156)
    warning_orange = (255, 165, 0)
    
    # 绘制标题
    title_text = "📦 用户背包"
    try:
        title_w, title_h = draw.textbbox((0, 0), title_text, font=title_font)[2:4]
    except:
        title_w, title_h = 200, 40
    draw.text(((width - title_w) // 2, 50), title_text, font=title_font, fill=primary_dark)
    
    # 用户信息
    nickname = user_data.get('nickname', '未知用户')
    user_text = f"用户: {nickname}"
    draw.text((50, 120), user_text, font=content_font, fill=primary_dark)
    
    # 统计信息（使用实际总数）
    rods_count = user_data.get('total_rods', len(user_data.get('rods', [])))
    accessories_count = user_data.get('total_accessories', len(user_data.get('accessories', [])))
    baits_count = user_data.get('total_baits', len(user_data.get('baits', [])))
    items_count = user_data.get('total_items', len(user_data.get('items', [])))
    
    stats_text = f"鱼竿: {rods_count} | 饰品: {accessories_count} | 鱼饵: {baits_count} | 道具: {items_count}"
    draw.text((50, 160), stats_text, font=content_font, fill=text_secondary)
    
    # 提示信息
    notice_text = "⚠️ 背包物品过多，图片生成超时！"
    draw.text((50, 220), notice_text, font=content_font, fill=warning_orange)
    
    hint1_text = "💡 建议操作："
    draw.text((50, 260), hint1_text, font=content_font, fill=primary_dark)
    
    hint2_text = "1. 使用分类命令查看（会自动过滤只显示5星以上装备）"
    draw.text((70, 290), hint2_text, font=small_font, fill=text_secondary)
    
    hint3_text = "2. 及时清理低品质装备（出售所有鱼竿/饰品）"
    draw.text((70, 320), hint3_text, font=small_font, fill=text_secondary)
    
    hint4_text = "3. 使用或出售多余的鱼饵和道具"
    draw.text((70, 350), hint4_text, font=small_font, fill=text_secondary)
    
    # 底部时间
    footer_text = f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        footer_w, footer_h = draw.textbbox((0, 0), footer_text, font=small_font)[2:4]
    except:
        footer_w, footer_h = 250, 20
    draw.text(((width - footer_w) // 2, height - 50), footer_text, font=small_font, fill=text_secondary)
    
    return image
