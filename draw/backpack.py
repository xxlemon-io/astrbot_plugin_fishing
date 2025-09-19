import os
from datetime import datetime
from typing import Dict, Any, List
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def format_rarity_display(rarity: int) -> str:
    """格式化稀有度显示，支持显示到10星，10星以上显示为★★★★★★★★★★+"""
    if rarity <= 10:
        return '★' * rarity
    else:
        return '★★★★★★★★★★+'

def draw_backpack_image(user_data: Dict[str, Any]) -> Image.Image:
    """
    绘制用户背包图像
    
    Args:
        user_data: 包含用户背包信息的字典，包括：
            - user_id: 用户ID
            - nickname: 用户昵称
            - rods: 鱼竿列表
            - accessories: 饰品列表
            - baits: 鱼饵列表
    
    Returns:
        PIL.Image.Image: 生成的背包图像
    """
    # 画布尺寸 
    width, height = 800, 1000
    
    # 1. 创建渐变背景
    def create_vertical_gradient(w, h, top_color, bottom_color):
        base = Image.new('RGB', (w, h), top_color)
        top_r, top_g, top_b = top_color
        bot_r, bot_g, bot_b = bottom_color
        draw = ImageDraw.Draw(base)
        for y in range(h):
            ratio = y / (h - 1)
            r = int(top_r + (bot_r - top_r) * ratio)
            g = int(top_g + (bot_g - top_g) * ratio)
            b = int(top_b + (bot_b - top_b) * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        return base

    bg_top = (174, 214, 241)  # 柔和天蓝色
    bg_bot = (245, 251, 255)  # 温和淡蓝色
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)

    # 2. 加载字体
    def load_font(name, size):
        path = os.path.join(os.path.dirname(__file__), "resource", name)
        try:
            return ImageFont.truetype(path, size)
        except Exception as e:
            return ImageFont.load_default()

    title_font = load_font("DouyinSansBold.otf", 32)
    subtitle_font = load_font("DouyinSansBold.otf", 24)
    content_font = load_font("DouyinSansBold.otf", 18)
    small_font = load_font("DouyinSansBold.otf", 16)
    tiny_font = load_font("DouyinSansBold.otf", 14)

    # 3. 颜色定义 - 温和协调的海洋主题配色
    primary_dark = (52, 73, 94)      # 温和深蓝 - 主标题
    primary_medium = (74, 105, 134)  # 柔和中蓝 - 副标题
    primary_light = (108, 142, 191)  # 淡雅蓝 - 强调色
    
    # 文本色：和谐灰蓝色系
    text_primary = (55, 71, 79)      # 温和深灰 - 主要文本
    text_secondary = (120, 144, 156) # 柔和灰蓝 - 次要文本
    text_muted = (176, 190, 197)     # 温和浅灰 - 弱化文本
    
    # 状态色：柔和自然色系
    success_color = (76, 175, 80)    # 温和绿 - 成功/积极状态
    warning_color = (255, 183, 77)   # 柔和橙 - 警告/中性
    error_color = (229, 115, 115)    # 温和红 - 错误/消极状态
    
    # 背景色：更柔和的对比
    card_bg = (255, 255, 255, 240)   # 高透明度白色
    
    # 特殊色：温和特色
    gold_color = (240, 173, 78)      # 温和金色 - 金币
    rare_color = (149, 117, 205)     # 柔和紫色 - 稀有物品

    # 4. 获取文本尺寸的辅助函数
    def get_text_size(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
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
    title_text = "🎒 用户背包"
    title_w, title_h = get_text_size(title_text, title_font)
    title_x = (width - title_w) // 2
    title_y = 20
    draw.text((title_x, title_y), title_text, font=title_font, fill=primary_dark)

    # 用户信息
    nickname = user_data.get('nickname', '未知用户')
    nickname_text = f"👤 {nickname}"
    draw.text((30, title_y + title_h + 15), nickname_text, font=subtitle_font, fill=primary_medium)

    current_y = title_y + title_h + 60

    # 鱼竿区域
    rods = user_data.get('rods', [])
    rod_section_y = current_y
    draw.text((30, rod_section_y), "🎣 鱼竿", font=subtitle_font, fill=primary_medium)
    current_y += 35

    if rods:
        # 计算鱼竿卡片布局 - 每行2个
        card_width = (width - 90) // 2
        card_height = 120
        card_margin = 15
        
        for i, rod in enumerate(rods):
            row = i // 2
            col = i % 2
            x = 30 + col * (card_width + card_margin)
            y = current_y + row * (card_height + card_margin)
            
            # 绘制鱼竿卡片
            draw_rounded_rectangle(draw, 
                                 (x, y, x + card_width, y + card_height), 
                                 8, fill=card_bg)
            
            # 鱼竿名称
            rod_name = rod['name'][:12] + "..." if len(rod['name']) > 12 else rod['name']
            draw.text((x + 10, y + 10), rod_name, font=content_font, fill=text_primary)
            
            # 稀有度和精炼等级
            rarity = rod.get('rarity', 1)
            refine_level = rod.get('refine_level', 1)
            star_color = rare_color if (rarity > 4 and refine_level > 4) else warning_color if rarity > 3 else text_secondary
            draw.text((x + 10, y + 35), f"{format_rarity_display(rarity)} Lv.{refine_level}", font=small_font, fill=star_color)
            
            # 装备状态
            is_equipped = rod.get('is_equipped', False)
            if is_equipped:
                draw.text((x + 10, y + 55), "✅ 已装备", font=small_font, fill=success_color)
            else:
                draw.text((x + 10, y + 55), "⭕ 未装备", font=small_font, fill=text_muted)
            
            # 属性加成
            if rod.get('bonus_rare_fish_chance', 0) > 0:
                bonus_text = f"稀有鱼+{rod['bonus_rare_fish_chance']:.1%}"
                draw.text((x + 10, y + 80), bonus_text, font=tiny_font, fill=primary_light)
            
            # 实例ID
            instance_id = rod.get('instance_id', 'N/A')
            draw.text((x + 10, y + 95), f"ID: {instance_id}", font=tiny_font, fill=text_secondary)
        
        # 更新当前Y位置
        rows = (len(rods) + 1) // 2
        current_y += rows * (card_height + card_margin)
    else:
        draw.text((30, current_y), "🎣 您还没有鱼竿，快去商店购买或抽奖获得吧！", font=content_font, fill=text_muted)
        current_y += 50

    current_y += 20

    # 饰品区域
    accessories = user_data.get('accessories', [])
    draw.text((30, current_y), "💍 饰品", font=subtitle_font, fill=primary_medium)
    current_y += 35

    if accessories:
        # 计算饰品卡片布局 - 每行2个
        card_width = (width - 90) // 2
        card_height = 120
        card_margin = 15
        
        for i, accessory in enumerate(accessories):
            row = i // 2
            col = i % 2
            x = 30 + col * (card_width + card_margin)
            y = current_y + row * (card_height + card_margin)
            
            # 绘制饰品卡片
            draw_rounded_rectangle(draw, 
                                 (x, y, x + card_width, y + card_height), 
                                 8, fill=card_bg)
            
            # 饰品名称
            acc_name = accessory['name'][:12] + "..." if len(accessory['name']) > 12 else accessory['name']
            draw.text((x + 10, y + 10), acc_name, font=content_font, fill=text_primary)
            
            # 稀有度和精炼等级
            rarity = accessory.get('rarity', 1)
            refine_level = accessory.get('refine_level', 1)
            star_color = rare_color if (rarity > 4 and refine_level > 4) else warning_color if rarity > 3 else text_secondary
            draw.text((x + 10, y + 35), f"{format_rarity_display(rarity)} Lv.{refine_level}", font=small_font, fill=star_color)
            
            # 装备状态
            is_equipped = accessory.get('is_equipped', False)
            if is_equipped:
                draw.text((x + 10, y + 55), "✅ 已装备", font=small_font, fill=success_color)
            else:
                draw.text((x + 10, y + 55), "⭕ 未装备", font=small_font, fill=text_muted)
            
            # 属性加成
            if accessory.get('bonus_coin_modifier', 0) > 0:
                bonus_text = f"金币+{accessory['bonus_coin_modifier']:.1%}"
                draw.text((x + 10, y + 80), bonus_text, font=tiny_font, fill=gold_color)
            
            # 实例ID
            instance_id = accessory.get('instance_id', 'N/A')
            draw.text((x + 10, y + 95), f"ID: {instance_id}", font=tiny_font, fill=text_secondary)
        
        # 更新当前Y位置
        rows = (len(accessories) + 1) // 2
        current_y += rows * (card_height + card_margin)
    else:
        draw.text((30, current_y), "💍 您还没有饰品，快去商店购买或抽奖获得吧！", font=content_font, fill=text_muted)
        current_y += 50

    current_y += 20

    # 鱼饵区域
    baits = user_data.get('baits', [])
    draw.text((30, current_y), "🐟 鱼饵", font=subtitle_font, fill=primary_medium)
    current_y += 35

    if baits:
        # 计算鱼饵卡片布局 - 每行3个
        card_width = (width - 120) // 3
        card_height = 100
        card_margin = 10
        
        for i, bait in enumerate(baits):
            row = i // 3
            col = i % 3
            x = 30 + col * (card_width + card_margin)
            y = current_y + row * (card_height + card_margin)
            
            # 绘制鱼饵卡片
            draw_rounded_rectangle(draw, 
                                 (x, y, x + card_width, y + card_height), 
                                 6, fill=card_bg)
            
            # 鱼饵名称
            bait_name = bait['name'][:8] + "..." if len(bait['name']) > 8 else bait['name']
            draw.text((x + 8, y + 8), bait_name, font=small_font, fill=text_primary)
            
            # 稀有度
            rarity = bait.get('rarity', 1)
            star_color = rare_color if rarity > 4 else warning_color if rarity >= 3 else text_secondary
            draw.text((x + 8, y + 25), format_rarity_display(rarity), font=tiny_font, fill=star_color)
            
            # 数量
            quantity = bait.get('quantity', 0)
            draw.text((x + 8, y + 40), f"数量: {quantity}", font=tiny_font, fill=text_secondary)
            
            # 持续时间
            duration = bait.get('duration_minutes', 0)
            if duration > 0:
                draw.text((x + 8, y + 55), f"持续: {duration}分钟", font=tiny_font, fill=primary_light)
            
            # 鱼饵ID
            bait_id = bait.get('bait_id', 'N/A')
            draw.text((x + 8, y + 80), f"ID: {bait_id}", font=tiny_font, fill=text_muted)
        
        # 更新当前Y位置
        rows = (len(baits) + 2) // 3
        current_y += rows * (card_height + card_margin)
    else:
        draw.text((30, current_y), "🐟 您还没有鱼饵，快去商店购买或抽奖获得吧！", font=content_font, fill=text_muted)
        current_y += 50

    # 底部信息
    current_y += 20
    footer_text = f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    footer_w, footer_h = get_text_size(footer_text, small_font)
    footer_x = (width - footer_w) // 2
    draw.text((footer_x, current_y), footer_text, font=small_font, fill=text_secondary)

    # 添加装饰性元素
    corner_size = 15
    corner_color = (255, 255, 255, 80)
    
    # 四角装饰
    draw.ellipse([8, 8, 8 + corner_size, 8 + corner_size], fill=corner_color)
    draw.ellipse([width - 8 - corner_size, 8, width - 8, 8 + corner_size], fill=corner_color)
    draw.ellipse([8, height - 8 - corner_size, 8 + corner_size, height - 8], fill=corner_color)
    draw.ellipse([width - 8 - corner_size, height - 8 - corner_size, width - 8, height - 8], fill=corner_color)

    return image


def get_user_backpack_data(inventory_service, user_id: str) -> Dict[str, Any]:
    """
    获取用户背包数据
    
    Args:
        inventory_service: 库存服务
        user_id: 用户ID
    
    Returns:
        包含用户背包信息的字典
    """
    # 获取鱼竿库存
    rod_result = inventory_service.get_user_rod_inventory(user_id)
    rods = rod_result.get('rods', []) if rod_result.get('success') else []
    
    # 获取饰品库存
    accessory_result = inventory_service.get_user_accessory_inventory(user_id)
    accessories = accessory_result.get('accessories', []) if accessory_result.get('success') else []
    
    # 获取鱼饵库存
    bait_result = inventory_service.get_user_bait_inventory(user_id)
    baits = bait_result.get('baits', []) if bait_result.get('success') else []
    
    return {
        'user_id': user_id,
        'nickname': user_id,  # 这里可以后续从用户服务获取昵称
        'rods': rods,
        'accessories': accessories,
        'baits': baits
    }
