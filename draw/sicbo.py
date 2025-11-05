"""
骰宝游戏图片生成模块
用于生成骰宝游戏相关的各种图片消息
"""

import os
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, List, Optional
from .gradient_utils import create_vertical_gradient
from .styles import (
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_GOLD,
    COLOR_TEXT_DARK, COLOR_TEXT_WHITE, COLOR_CARD_BG,
    load_font
)


def draw_sicbo_game_start(countdown_seconds: int) -> Image.Image:
    """绘制骰宝游戏开始图片"""
    width, height = 600, 400
    
    # 创建渐变背景
    bg_top = (255, 182, 193)  # 浅粉红
    bg_bot = (255, 239, 213)  # 杏仁白
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = load_font(36)
    subtitle_font = load_font(24)
    content_font = load_font(20)
    
    # 绘制标题
    title_text = "🎲 骰宝游戏开始！"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 50), title_text, fill=COLOR_TEXT_DARK, font=title_font)
    
    # 绘制倒计时信息
    countdown_text = f"⏰ 倒计时：{countdown_seconds} 秒"
    countdown_bbox = draw.textbbox((0, 0), countdown_text, font=subtitle_font)
    countdown_width = countdown_bbox[2] - countdown_bbox[0]
    countdown_x = (width - countdown_width) // 2
    draw.text((countdown_x, 120), countdown_text, fill=COLOR_WARNING, font=subtitle_font)
    
    # 绘制提示信息
    tips = [
        "📢 快来下注吧！",
        "💰 支持多种下注方式",
        "🎯 大小单双 (1:1)",
        "🐅 豹子 (1:24)",
        "📊 指定点数 (高赔率)"
    ]
    
    tip_y = 180
    for tip in tips:
        tip_bbox = draw.textbbox((0, 0), tip, font=content_font)
        tip_width = tip_bbox[2] - tip_bbox[0]
        tip_x = (width - tip_width) // 2
        draw.text((tip_x, tip_y), tip, fill=COLOR_TEXT_DARK, font=content_font)
        tip_y += 30
    
    return image


def draw_sicbo_bet_confirmation(bet_type: str, amount: int, username: str) -> Image.Image:
    """绘制下注确认图片"""
    width, height = 500, 300
    
    # 创建渐变背景
    bg_top = (152, 251, 152)  # 浅绿色
    bg_bot = (240, 255, 240)  # 蜜瓜绿
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = load_font(28)
    content_font = load_font(20)
    
    # 绘制标题
    title_text = "✅ 下注成功！"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 40), title_text, fill=COLOR_SUCCESS, font=title_font)
    
    # 绘制下注信息
    bet_info = [
        f"👤 玩家：{username}",
        f"🎯 下注类型：{bet_type}",
        f"💰 下注金额：{int(amount):,} 金币"
    ]
    
    info_y = 100
    for info in bet_info:
        info_bbox = draw.textbbox((0, 0), info, font=content_font)
        info_width = info_bbox[2] - info_bbox[0]
        info_x = (width - info_width) // 2
        draw.text((info_x, info_y), info, fill=COLOR_TEXT_DARK, font=content_font)
        info_y += 35
    
    # 绘制祝福语
    luck_text = "🍀 祝您好运！"
    luck_bbox = draw.textbbox((0, 0), luck_text, font=content_font)
    luck_width = luck_bbox[2] - luck_bbox[0]
    luck_x = (width - luck_width) // 2
    draw.text((luck_x, 230), luck_text, fill=COLOR_GOLD, font=content_font)
    
    return image


def draw_sicbo_bet_merged(bet_type: str, current_amount: int, original_amount: int, new_total: int, username: str) -> Image.Image:
    """绘制合并下注确认图片"""
    width, height = 550, 380
    
    # 创建渐变背景 - 使用更温暖的橙色系表示合并
    bg_top = (255, 218, 185)  # 桃色
    bg_bot = (255, 239, 213)  # 杏仁白
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = load_font(28)
    content_font = load_font(20)
    highlight_font = load_font(22)
    
    # 绘制标题
    title_text = "✅ 下注成功！(已合并)"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 30), title_text, fill=COLOR_SUCCESS, font=title_font)
    
    # 绘制玩家信息
    player_text = f"👤 玩家：{username}"
    player_bbox = draw.textbbox((0, 0), player_text, font=content_font)
    player_width = player_bbox[2] - player_bbox[0]
    player_x = (width - player_width) // 2
    draw.text((player_x, 80), player_text, fill=COLOR_TEXT_DARK, font=content_font)
    
    # 绘制下注类型
    type_text = f"🎯 下注类型：{bet_type}"
    type_bbox = draw.textbbox((0, 0), type_text, font=content_font)
    type_width = type_bbox[2] - type_bbox[0]
    type_x = (width - type_width) // 2
    draw.text((type_x, 115), type_text, fill=COLOR_TEXT_DARK, font=content_font)
    
    # 绘制合并信息
    merge_info = [
        f"💰 本次下注：{int(current_amount):,} 金币",
        f"📈 原有下注：{int(original_amount):,} 金币",
        f"🏆 合并后总额：{int(new_total):,} 金币"
    ]
    
    info_y = 160
    for i, info in enumerate(merge_info):
        # 最后一行用高亮字体和颜色
        font = highlight_font if i == 2 else content_font
        color = COLOR_GOLD if i == 2 else COLOR_TEXT_DARK
        
        info_bbox = draw.textbbox((0, 0), info, font=font)
        info_width = info_bbox[2] - info_bbox[0]
        info_x = (width - info_width) // 2
        draw.text((info_x, info_y), info, fill=color, font=font)
        info_y += 35
    
    # 绘制提示信息
    tip_text = "💡 相同类型下注已自动合并"
    tip_bbox = draw.textbbox((0, 0), tip_text, font=content_font)
    tip_width = tip_bbox[2] - tip_bbox[0]
    tip_x = (width - tip_width) // 2
    draw.text((tip_x, 290), tip_text, fill=COLOR_WARNING, font=content_font)
    
    # 绘制祝福语
    luck_text = "🍀 祝您好运！"
    luck_bbox = draw.textbbox((0, 0), luck_text, font=content_font)
    luck_width = luck_bbox[2] - luck_bbox[0]
    luck_x = (width - luck_width) // 2
    draw.text((luck_x, 330), luck_text, fill=COLOR_GOLD, font=content_font)
    
    return image
    
    # 绘制祝福语
    luck_text = "🍀 祝您好运！"
    luck_bbox = draw.textbbox((0, 0), luck_text, font=content_font)
    luck_width = luck_bbox[2] - luck_bbox[0]
    luck_x = (width - luck_width) // 2
    draw.text((luck_x, 230), luck_text, fill=COLOR_GOLD, font=content_font)
    
    return image


def draw_sicbo_status(game_data: Dict[str, Any]) -> Image.Image:
    """绘制骰宝游戏状态图片"""
    width, height = 650, 500
    
    # 创建渐变背景
    bg_top = (173, 216, 230)  # 浅蓝色
    bg_bot = (240, 248, 255)  # 爱丽丝蓝
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = load_font(32)
    subtitle_font = load_font(24)
    content_font = load_font(18)
    small_font = load_font(16)
    
    # 绘制标题
    title_text = "🎲 骰宝游戏状态"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 30), title_text, fill=COLOR_TEXT_DARK, font=title_font)
    
    # 绘制游戏信息
    remaining_time = game_data.get('remaining_time', 0)
    total_bets = game_data.get('total_bets', 0)
    total_amount = game_data.get('total_amount', 0)
    
    info_y = 100
    
    # 剩余时间
    time_text = f"⏰ 剩余时间：{remaining_time} 秒"
    draw.text((50, info_y), time_text, fill=COLOR_WARNING, font=subtitle_font)
    info_y += 40
    
    # 下注统计
    stats_text = f"📊 总下注：{total_bets} 笔，共 {int(total_amount):,} 金币"
    draw.text((50, info_y), stats_text, fill=COLOR_TEXT_DARK, font=content_font)
    info_y += 50
    
    # 下注详情
    bets = game_data.get('bets', {})
    if bets:
        detail_title = "📋 下注详情："
        draw.text((50, info_y), detail_title, fill=COLOR_TEXT_DARK, font=subtitle_font)
        info_y += 35
        
        for bet_type, bet_info in bets.items():
            count = bet_info.get('count', 0)
            amount = bet_info.get('amount', 0)
            if count > 0:
                bet_detail = f"  • {bet_type}：{count} 笔，{int(amount):,} 金币"
                draw.text((70, info_y), bet_detail, fill=COLOR_TEXT_DARK, font=content_font)
                info_y += 25
    else:
        no_bets_text = "💭 暂无下注"
        draw.text((50, info_y), no_bets_text, fill=COLOR_TEXT_DARK, font=content_font)
    
    return image


def draw_sicbo_result(dice1: int, dice2: int, dice3: int, results: List[Dict], player_results: List[Dict]) -> Image.Image:
    """绘制骰宝开奖结果图片
    
    Args:
        dice1, dice2, dice3: 三个骰子的点数
        results: 游戏结果（暂未使用）
        player_results: 玩家结果列表，每个元素包含 username 和 profit
    """
    # 根据玩家数量动态调整高度
    base_height = 400
    player_height = len(player_results) * 25 + 100 if player_results else 50
    width, height = 700, max(base_height, base_height + player_height)
    
    # 创建渐变背景
    bg_top = (255, 215, 0)    # 金色
    bg_bot = (255, 248, 220)  # 玉米丝色
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = load_font(36)
    dice_font = load_font(48)
    subtitle_font = load_font(24)
    content_font = load_font(18)
    
    # 绘制标题
    title_text = "🎉 骰宝开奖结果"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 30), title_text, fill=COLOR_TEXT_DARK, font=title_font)
    
    # 绘制骰子结果
    dice_y = 100
    total_points = dice1 + dice2 + dice3
    
    # 骰子图案
    dice_text = f"🎲 {dice1}  🎲 {dice2}  🎲 {dice3}"
    dice_bbox = draw.textbbox((0, 0), dice_text, font=dice_font)
    dice_width = dice_bbox[2] - dice_bbox[0]
    dice_x = (width - dice_width) // 2
    draw.text((dice_x, dice_y), dice_text, fill=COLOR_ERROR, font=dice_font)
    
    # 总点数
    total_text = f"总点数：{total_points}"
    total_bbox = draw.textbbox((0, 0), total_text, font=subtitle_font)
    total_width = total_bbox[2] - total_bbox[0]
    total_x = (width - total_width) // 2
    draw.text((total_x, dice_y + 70), total_text, fill=COLOR_TEXT_DARK, font=subtitle_font)
    
    # 中奖类型
    result_y = dice_y + 120
    win_types = []
    
    # 判断大小
    if total_points >= 11:
        win_types.append("大")
    else:
        win_types.append("小")
    
    # 判断单双
    if total_points % 2 == 1:
        win_types.append("单")
    else:
        win_types.append("双")
    
    # 判断豹子
    if dice1 == dice2 == dice3:
        win_types.append("豹子")
    
    win_text = f"🏆 中奖类型：{' | '.join(win_types)}"
    win_bbox = draw.textbbox((0, 0), win_text, font=subtitle_font)
    win_width = win_bbox[2] - win_bbox[0]
    win_x = (width - win_width) // 2
    draw.text((win_x, result_y), win_text, fill=COLOR_SUCCESS, font=subtitle_font)
    
    # 玩家结果
    players_y = result_y + 60
    if player_results:
        # 分离盈利和亏损玩家
        winners = [(p['username'], p['profit']) for p in player_results if p['profit'] > 0]
        losers = [(p['username'], p['profit']) for p in player_results if p['profit'] < 0]
        
        # 显示中奖玩家
        if winners:
            winners_title = "🎊 中奖玩家："
            draw.text((50, players_y), winners_title, fill=COLOR_TEXT_DARK, font=subtitle_font)
            players_y += 35
            
            for username, profit in winners[:8]:  # 最多显示8个，避免图片过长
                winner_text = f"  🏅 {username}：+{int(profit):,} 金币"
                draw.text((70, players_y), winner_text, fill=COLOR_SUCCESS, font=content_font)
                players_y += 25
                
            if len(winners) > 8:
                more_text = f"  ... 还有 {len(winners) - 8} 位中奖者"
                draw.text((70, players_y), more_text, fill=COLOR_TEXT_DARK, font=content_font)
                players_y += 25
        
        # 显示未中奖玩家
        if losers:
            if winners:
                players_y += 10  # 间隔
            losers_title = "💸 未中奖玩家："
            draw.text((50, players_y), losers_title, fill=COLOR_TEXT_DARK, font=subtitle_font)
            players_y += 35
            
            for username, loss in losers[:8]:  # 最多显示8个
                loser_text = f"  💔 {username}：{int(loss):,} 金币"
                draw.text((70, players_y), loser_text, fill=COLOR_ERROR, font=content_font)
                players_y += 25
                
            if len(losers) > 8:
                more_text = f"  ... 还有 {len(losers) - 8} 位未中奖者"
                draw.text((70, players_y), more_text, fill=COLOR_TEXT_DARK, font=content_font)
    else:
        no_player_text = "🤔 本局无人参与"
        no_player_bbox = draw.textbbox((0, 0), no_player_text, font=subtitle_font)
        no_player_width = no_player_bbox[2] - no_player_bbox[0]
        no_player_x = (width - no_player_width) // 2
        draw.text((no_player_x, players_y), no_player_text, fill=COLOR_TEXT_DARK, font=subtitle_font)
    
    return image


def draw_sicbo_user_bets(user_bets: List[Dict], username: str) -> Image.Image:
    """绘制用户下注情况图片"""
    width, height = 600, max(400, 200 + len(user_bets) * 30)
    
    # 创建渐变背景
    bg_top = (221, 160, 221)  # 梅红色
    bg_bot = (255, 240, 245)  # 薰衣草腮红
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = load_font(28)
    content_font = load_font(18)
    
    # 绘制标题
    title_text = f"📋 {username} 的下注情况"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 30), title_text, fill=COLOR_TEXT_DARK, font=title_font)
    
    # 绘制下注列表
    if user_bets:
        bet_y = 100
        total_amount = 0
        
        for i, bet in enumerate(user_bets, 1):
            bet_type = bet.get('bet_type', '未知')
            amount = bet.get('amount', 0)
            total_amount += amount
            
            bet_text = f"{i}. {bet_type}：{int(amount):,} 金币"
            draw.text((50, bet_y), bet_text, fill=COLOR_TEXT_DARK, font=content_font)
            bet_y += 30
        
        # 总计
        total_text = f"💰 总下注：{int(total_amount):,} 金币"
        draw.text((50, bet_y + 20), total_text, fill=COLOR_GOLD, font=content_font)
    else:
        no_bet_text = "💭 您还没有下注"
        no_bet_bbox = draw.textbbox((0, 0), no_bet_text, font=content_font)
        no_bet_width = no_bet_bbox[2] - no_bet_bbox[0]
        no_bet_x = (width - no_bet_width) // 2
        draw.text((no_bet_x, 120), no_bet_text, fill=COLOR_TEXT_DARK, font=content_font)
    
    return image


def draw_sicbo_countdown_setting(seconds: int, admin_name: str) -> Image.Image:
    """绘制倒计时设置成功图片"""
    width, height = 500, 300
    
    # 创建渐变背景
    bg_top = (135, 206, 235)  # 天空蓝
    bg_bot = (240, 248, 255)  # 爱丽丝蓝
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = load_font(28)
    content_font = load_font(20)
    
    # 绘制标题
    title_text = "⚙️ 设置成功！"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 50), title_text, fill=COLOR_SUCCESS, font=title_font)
    
    # 绘制设置信息
    info = [
        f"👤 管理员：{admin_name}",
        f"⏰ 新倒计时：{seconds} 秒",
        "✅ 设置已生效"
    ]
    
    info_y = 120
    for line in info:
        line_bbox = draw.textbbox((0, 0), line, font=content_font)
        line_width = line_bbox[2] - line_bbox[0]
        line_x = (width - line_width) // 2
        draw.text((line_x, info_y), line, fill=COLOR_TEXT_DARK, font=content_font)
        info_y += 35
    
    return image


def save_image_to_temp(image: Image.Image, filename: str, data_dir: str) -> str:
    """将图片保存到临时目录并返回路径"""
    temp_dir = os.path.join(data_dir, "temp_images")
    os.makedirs(temp_dir, exist_ok=True)
    
    # 使用时间戳确保文件名唯一
    import time
    timestamp = int(time.time() * 1000)
    image_path = os.path.join(temp_dir, f"{filename}_{timestamp}.png")
    
    image.save(image_path, "PNG")
    return image_path


def draw_sicbo_help(countdown_seconds: int) -> Image.Image:
    """绘制骰宝帮助图片"""
    width, height = 650, 800
    
    # 创建渐变背景 - 参考提供的蓝色系风格
    bg_top = (240, 248, 255)  # 浅蓝色
    bg_bot = (230, 242, 255)  # 稍深蓝色
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = load_font(32)
    section_font = load_font(24)
    content_font = load_font(18)
    small_font = load_font(16)
    
    # 绘制标题
    title_text = "🎲 骰宝游戏帮助"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 30), title_text, fill=(70, 130, 180), font=title_font)
    
    y_pos = 90
    
    # 游戏流程卡片
    card_height = 120
    card_rect = [30, y_pos, width-30, y_pos + card_height]
    draw.rounded_rectangle(card_rect, radius=10, fill=(255, 255, 255, 230), outline=(200, 220, 240), width=2)
    
    # 游戏流程标题
    draw.text((50, y_pos + 15), "📋 游戏流程", fill=(70, 130, 180), font=section_font)
    
    # 游戏流程内容
    flow_steps = [
        f"1. 管理员或玩家发送 \"/开庄\" 开启新游戏",
        f"2. 游戏倒计时{countdown_seconds}秒，期间玩家可自由下注",
        "3. 倒计时结束后自动开奖并结算"
    ]
    
    step_y = y_pos + 45
    for step in flow_steps:
        draw.text((70, step_y), step, fill=COLOR_TEXT_DARK, font=content_font)
        step_y += 22
    
    y_pos += card_height + 20
    
    # 下注类型卡片
    card_height = 180
    card_rect = [30, y_pos, width-30, y_pos + card_height]
    draw.rounded_rectangle(card_rect, radius=10, fill=(255, 255, 255, 230), outline=(200, 220, 240), width=2)
    
    # 下注类型标题
    draw.text((50, y_pos + 15), "🎯 下注类型", fill=(70, 130, 180), font=section_font)
    
    # 下注类型内容
    bet_types = [
        "• 大小单双：/鸭大 金额、/鸭小 金额、/鸭单 金额、/鸭双 金额",
        "• 豹子：/鸭豹子 金额 (三个骰子相同)",
        "• 指定点数：/鸭一点 金额、/鸭二点 金额 ... /鸭六点 金额",
        "• 总点数：/鸭4点 金额、/鸭5点 金额 ... /鸭17点 金额"
    ]
    
    type_y = y_pos + 45
    for bet_type in bet_types:
        # 分行显示长文本
        if len(bet_type) > 30:
            parts = bet_type.split('：')
            if len(parts) == 2:
                draw.text((70, type_y), parts[0] + '：', fill=COLOR_TEXT_DARK, font=content_font)
                type_y += 20
                draw.text((90, type_y), parts[1], fill=(100, 100, 100), font=small_font)
            else:
                draw.text((70, type_y), bet_type, fill=COLOR_TEXT_DARK, font=content_font)
        else:
            draw.text((70, type_y), bet_type, fill=COLOR_TEXT_DARK, font=content_font)
        type_y += 25
    
    y_pos += card_height + 20
    
    # 其他命令卡片
    card_height = 140
    card_rect = [30, y_pos, width-30, y_pos + card_height]
    draw.rounded_rectangle(card_rect, radius=10, fill=(255, 255, 255, 230), outline=(200, 220, 240), width=2)
    
    # 其他命令标题
    draw.text((50, y_pos + 15), "⚙️ 其他命令", fill=(70, 130, 180), font=section_font)
    
    # 其他命令内容
    commands = [
        "• /骰宝状态 - 查看当前游戏状态",
        "• /我的下注 - 查看本局下注情况",
        "• /骰宝赔率 - 查看详细赔率表",
        "• /骰宝倒计时 [秒数] - 管理员设置倒计时时间"
    ]
    
    cmd_y = y_pos + 45
    for cmd in commands:
        draw.text((70, cmd_y), cmd, fill=COLOR_TEXT_DARK, font=content_font)
        cmd_y += 22
    
    y_pos += card_height + 20
    
    # 特殊规则卡片
    card_height = 100
    card_rect = [30, y_pos, width-30, y_pos + card_height]
    draw.rounded_rectangle(card_rect, radius=10, fill=(255, 250, 205, 230), outline=(255, 215, 0), width=2)
    
    # 特殊规则标题
    draw.text((50, y_pos + 15), "⚠️ 特殊规则", fill=(184, 134, 11), font=section_font)
    
    # 特殊规则内容
    rules = [
        "• 豹子杀大小：出现豹子时，大小单双全输",
        "• 支持中文数字：如 \"10万\" = \"100000\""
    ]
    
    rule_y = y_pos + 45
    for rule in rules:
        draw.text((70, rule_y), rule, fill=(184, 134, 11), font=content_font)
        rule_y += 22
    
    # 底部祝福语
    y_pos += card_height + 30
    luck_text = "🍀 祝您好运！"
    luck_bbox = draw.textbbox((0, 0), luck_text, font=section_font)
    luck_width = luck_bbox[2] - luck_bbox[0]
    luck_x = (width - luck_width) // 2
    draw.text((luck_x, y_pos), luck_text, fill=COLOR_GOLD, font=section_font)
    
    return image


def draw_sicbo_odds() -> Image.Image:
    """绘制骰宝赔率详情图片"""
    width, height = 700, 1200  # 增加高度以容纳所有内容
    
    # 创建渐变背景
    bg_top = (240, 248, 255)  # 浅蓝色
    bg_bot = (230, 242, 255)  # 稍深蓝色
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 加载字体
    title_font = load_font(32)
    section_font = load_font(24)
    content_font = load_font(18)
    small_font = load_font(16)
    
    # 绘制标题
    title_text = "💰 骰宝赔率详情"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 30), title_text, fill=(70, 130, 180), font=title_font)
    
    y_pos = 90
    
    # 大小单双赔率卡片
    card_height = 140
    card_rect = [30, y_pos, width-30, y_pos + card_height]
    draw.rounded_rectangle(card_rect, radius=10, fill=(255, 255, 255, 230), outline=(200, 220, 240), width=2)
    
    draw.text((50, y_pos + 15), "🎯 大小单双 (1:1)", fill=(70, 130, 180), font=section_font)
    
    dsdd_odds = [
        "• 鸭大：总点数11-17，赔率1:1",
        "• 鸭小：总点数4-10，赔率1:1",
        "• 鸭单：总点数为奇数，赔率1:1",
        "• 鸭双：总点数为偶数，赔率1:1"
    ]
    
    odds_y = y_pos + 45
    for odd in dsdd_odds:
        draw.text((70, odds_y), odd, fill=COLOR_TEXT_DARK, font=content_font)
        odds_y += 22
    
    y_pos += card_height + 20
    
    # 豹子赔率卡片
    card_height = 80
    card_rect = [30, y_pos, width-30, y_pos + card_height]
    draw.rounded_rectangle(card_rect, radius=10, fill=(255, 240, 245, 230), outline=(255, 20, 147), width=2)
    
    draw.text((50, y_pos + 15), "🐅 豹子 (1:24)", fill=(255, 20, 147), font=section_font)
    draw.text((70, y_pos + 45), "• 鸭豹子：三个骰子相同，赔率1:24", fill=COLOR_TEXT_DARK, font=content_font)
    
    y_pos += card_height + 20
    
    # 指定点数赔率卡片
    card_height = 140
    card_rect = [30, y_pos, width-30, y_pos + card_height]
    draw.rounded_rectangle(card_rect, radius=10, fill=(240, 255, 240, 230), outline=(34, 139, 34), width=2)
    
    draw.text((50, y_pos + 15), "🎲 指定点数 (动态赔率)", fill=(34, 139, 34), font=section_font)
    
    point_odds = [
        "• 鸭一点/二点/三点/四点/五点/六点：",
        "  - 出现1个该点数：赔率1:1",
        "  - 出现2个该点数：赔率1:2", 
        "  - 出现3个该点数：赔率1:3"
    ]
    
    point_y = y_pos + 45
    for odd in point_odds:
        draw.text((70, point_y), odd, fill=COLOR_TEXT_DARK, font=content_font)
        point_y += 22
    
    y_pos += card_height + 20
    
    # 总点数赔率卡片
    card_height = 450  # 增加卡片高度以容纳表格
    card_rect = [30, y_pos, width-30, y_pos + card_height]
    draw.rounded_rectangle(card_rect, radius=10, fill=(255, 248, 220, 230), outline=(255, 165, 0), width=2)
    
    draw.text((50, y_pos + 15), "📊 总点数赔率", fill=(255, 140, 0), font=section_font)
    
    # 总点数赔率表
    total_odds = [
        ("4点", "1:50", "17点", "1:50"),
        ("5点", "1:18", "16点", "1:18"),
        ("6点", "1:14", "15点", "1:14"),
        ("7点", "1:12", "14点", "1:12"),
        ("8点", "1:8", "13点", "1:8"),
        ("9点", "1:6", "12点", "1:6"),
        ("10点", "1:6", "11点", "1:6")
    ]
    
    # 绘制表头
    total_y = y_pos + 50
    draw.text((70, total_y), "点数", fill=(255, 140, 0), font=content_font)
    draw.text((150, total_y), "赔率", fill=(255, 140, 0), font=content_font)
    draw.text((350, total_y), "点数", fill=(255, 140, 0), font=content_font)
    draw.text((430, total_y), "赔率", fill=(255, 140, 0), font=content_font)
    
    total_y += 35  # 增加表头间距
    # 绘制分隔线
    draw.line([70, total_y, 550, total_y], fill=(255, 140, 0), width=1)
    total_y += 15  # 增加分隔线后间距
    
    # 绘制赔率数据
    for low_point, low_odds, high_point, high_odds in total_odds:
        draw.text((70, total_y), low_point, fill=COLOR_TEXT_DARK, font=content_font)
        draw.text((150, total_y), low_odds, fill=(220, 20, 60), font=content_font)
        draw.text((350, total_y), high_point, fill=COLOR_TEXT_DARK, font=content_font)
        draw.text((430, total_y), high_odds, fill=(220, 20, 60), font=content_font)
        total_y += 30  # 增加行间距
    
    y_pos += card_height + 20
    
    # 特殊说明卡片
    card_height = 120  # 增加卡片高度
    card_rect = [30, y_pos, width-30, y_pos + card_height]
    draw.rounded_rectangle(card_rect, radius=10, fill=(255, 245, 238, 230), outline=(255, 69, 0), width=2)
    
    draw.text((50, y_pos + 15), "⚠️ 重要提醒", fill=(255, 69, 0), font=section_font)
    
    notes = [
        "• 豹子杀大小：出现豹子时，大小单双全部输掉",
        "• 赔率为净赔率，不包含本金"
    ]
    
    note_y = y_pos + 50  # 增加标题和内容间距
    for note in notes:
        draw.text((70, note_y), note, fill=(255, 69, 0), font=content_font)
        note_y += 25  # 增加行间距
    
    return image