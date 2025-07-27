import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from io import BytesIO
import time

def draw_state_image(user_data: Dict[str, Any]) -> Image.Image:
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
    Returns:
        PIL.Image.Image: 生成的状态图像
    """
    # 画布尺寸 
    width, height = 620, 540
    
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

    title_font = load_font("DouyinSansBold.otf", 28)
    subtitle_font = load_font("DouyinSansBold.otf", 24)
    content_font = load_font("DouyinSansBold.otf", 20)
    small_font = load_font("DouyinSansBold.otf", 16)
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
        if avatar_image := get_user_avatar(user_id, avatar_size):
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

        draw.text((col1_x + nickname_width + 10, row1_y + height_offset), title_text, font=small_font, fill=rare_color)
    # else:
    #     title_text = "未装备
    #     draw.text((col1_x + nickname_width + 10, row1_y + height_offset), title_text, font=small_font, fill=text_color)
    
    # 金币
    coins = user_data.get('coins', 0)
    coins_text = f"金币: {coins:,}"
    draw.text((col1_x, row2_y), coins_text, font=small_font, fill=gold_color)
    
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
        draw.text((left_col_x, equipment_row2_y), rod_name, font=content_font, fill=text_primary)
        # 根据稀有度选择颜色
        rarity = current_rod.get('rarity', 1)
        refined_level = current_rod.get('refine_level', 1)
        star_color = rare_color if (rarity > 4 and refined_level > 4) else warning_color if rarity > 3 else text_secondary
        draw.text((left_col_x, equipment_row3_y), f"{'★' * min(rarity, 5)} Lv.{refined_level}", font=tiny_font, fill=star_color)
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
        star_color = rare_color if (rarity > 4 and refined_level > 4) else warning_color if rarity > 3 else text_secondary
        draw.text((left_col_x, equipment_row6_y), f"{'★' * min(rarity, 5)} Lv.{refined_level}", font=tiny_font, fill=star_color)
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
        bait_detail = f"{'★' * min(rarity, 5)} 剩余：{current_bait.get('quantity', 0)}"
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

    # 定义状态信息的网格位置 - 两列布局
    status_col1_x = card_margin + 15    # 左列
    status_col2_x = card_margin + 315   # 右列
    status_row1_y = current_y + 12      # 第一行
    status_row2_y = current_y + 35      # 第二行
    status_row3_y = current_y + 81      # 鱼塘信息 

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

    # 第三行：鱼塘信息
    pond_info = user_data.get('pond_info', {})
    if pond_info and pond_info.get('total_count', 0) > 0:
        # 左列：鱼塘鱼数
        pond_count_text = f"鱼塘数量: {pond_info['total_count']} 条， 价值: {pond_info['total_value']:,} 金币"
        draw.text((status_col1_x, status_row3_y), pond_count_text, font=content_font, fill=text_primary)
    else:
        # 鱼塘为空时显示
        pond_empty_text = "鱼塘里什么都没有..."
        draw.text((status_col1_x, status_row3_y), pond_empty_text, font=content_font, fill=text_muted)


    # 10. 底部信息 - 调整位置
    current_y += status_card_height + 15
    footer_text = f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    footer_w, footer_h = get_text_size(footer_text, small_font)
    footer_x = (width - footer_w) // 2
    draw.text((footer_x, current_y), footer_text, font=small_font, fill=text_secondary)

    # 12. 添加装饰性元素 - 保持简洁
    corner_size = 15  # 稍微减小装饰元素
    corner_color = (255, 255, 255, 80)
    
    # 四角装饰
    draw.ellipse([8, 8, 8 + corner_size, 8 + corner_size], fill=corner_color)
    draw.ellipse([width - 8 - corner_size, 8, width - 8, 8 + corner_size], fill=corner_color)
    draw.ellipse([8, height - 8 - corner_size, 8 + corner_size, height - 8], fill=corner_color)
    draw.ellipse([width - 8 - corner_size, height - 8 - corner_size, width - 8, height - 8], fill=corner_color)

    return image


def get_user_state_data(user_repo, inventory_repo, item_template_repo, log_repo, game_config, user_id: str) -> Optional[Dict[str, Any]]:
    """
    获取用户状态数据
    
    Args:
        user_repo: 用户仓储
        inventory_repo: 库存仓储
        item_template_repo: 物品模板仓储
        log_repo: 日志仓储
        game_config: 游戏配置
        user_id: 用户ID
    
    Returns:
        包含用户状态信息的字典，如果用户不存在则返回None
    """
    from ..core.utils import get_now
    
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
            current_rod = {
                'name': rod_template.name,
                'rarity': rod_template.rarity,
                'refine_level': rod_instance.refine_level
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
    try:
        max_attempts_per_day = game_config.get("wipe_bomb", {}).get("max_attempts_per_day", 3)
        
        # 使用与game_mechanics_service相同的方法获取今日已使用次数
        used_attempts_today = log_repo.get_wipe_bomb_log_count_today(user_id)
        wipe_bomb_remaining = max(0, max_attempts_per_day - used_attempts_today)
    except Exception as e:
        # 如果计算失败，默认为最大次数
        wipe_bomb_remaining = max_attempts_per_day
    
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
        'current_rod': current_rod,
        'current_accessory': current_accessory,
        'current_bait': current_bait,
        'auto_fishing_enabled': user.auto_fishing_enabled,
        'steal_cooldown_remaining': steal_cooldown_remaining,
        'fishing_zone': fishing_zone,
        'current_title': current_title,
        'total_fishing_count': total_fishing_count,
        'steal_total_value': steal_total_value,
        'signed_in_today': signed_in_today,
        'wipe_bomb_remaining': wipe_bomb_remaining,
        'pond_info': pond_info
    }

def get_user_avatar(user_id: str, avatar_size: int = 50) -> Optional[Image.Image]:
    """
    获取用户头像并处理为圆形
    
    Args:
        user_id: 用户ID
        avatar_size: 头像尺寸
    
    Returns:
        处理后的头像图像，如果失败返回None
    """
    try:
        # 创建头像缓存目录
        cache_dir = os.path.join("data/plugin_data/astrbot_plugin_fishing", "avatar_cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        avatar_cache_path = os.path.join(cache_dir, f"{user_id}_avatar.png")
        
        # 检查是否有缓存的头像（24小时刷新）
        avatar_image = None
        if os.path.exists(avatar_cache_path):
            try:
                file_age = time.time() - os.path.getmtime(avatar_cache_path)
                if file_age < 86400:  # 24小时
                    avatar_image = Image.open(avatar_cache_path).convert('RGBA')
            except:
                pass
        
        # 如果没有缓存或缓存过期，重新下载
        if avatar_image is None:
            avatar_url = f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"
            response = requests.get(avatar_url, timeout=2) # 2s超时
            if response.status_code == 200:
                avatar_image = Image.open(BytesIO(response.content)).convert('RGBA')
                # 保存到缓存
                avatar_image.save(avatar_cache_path, 'PNG')
        
        if avatar_image:
            return avatar_postprocess(avatar_image, avatar_size)
        
    except Exception as e:
        pass
    
    return None

def avatar_postprocess(avatar_image: Image.Image, size: int) -> Image.Image:
    """
    将头像处理为指定大小的圆角头像，抗锯齿效果
    """
    # 调整头像大小
    avatar_image = avatar_image.resize((size, size), Image.Resampling.LANCZOS)
    
    # 使用更合适的圆角半径
    corner_radius = size // 8  # 稍微减小圆角，看起来更自然
    
    # 抗锯齿处理
    scale_factor = 4
    large_size = size * scale_factor
    large_radius = corner_radius * scale_factor
    
    # 创建高质量遮罩
    large_mask = Image.new('L', (large_size, large_size), 0)
    large_draw = ImageDraw.Draw(large_mask)
    
    # 绘制圆角矩形
    large_draw.rounded_rectangle(
        [0, 0, large_size, large_size], 
        radius=large_radius, 
        fill=255
    )
    
    # 高质量缩放
    mask = large_mask.resize((size, size), Image.Resampling.LANCZOS)
    avatar_image.putalpha(mask)
    
    return avatar_image