"""
骰宝游戏处理器
处理所有骰宝相关的命令
"""

from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger
from typing import TYPE_CHECKING
from ..draw.sicbo import (
    draw_sicbo_game_start, draw_sicbo_bet_confirmation, draw_sicbo_bet_merged, draw_sicbo_status,
    draw_sicbo_result, draw_sicbo_user_bets, draw_sicbo_countdown_setting, draw_sicbo_help,
    draw_sicbo_odds, save_image_to_temp
)

if TYPE_CHECKING:
    from ..main import FishingPlugin


async def start_sicbo_game(plugin: "FishingPlugin", event: AstrMessageEvent):
    """开庄命令"""
    try:
        # 获取游戏会话ID - 使用unified_msg_origin确保会话唯一性
        game_session_id = event.unified_msg_origin
        
        # 构建会话信息
        session_info = {
            'platform': getattr(event.platform_meta, 'platform_name', 'aiocqhttp'),
            'session_id': event.session_id,
            'sender_id': event.get_sender_id(),
            'unified_msg_origin': event.unified_msg_origin,
        }
        
        # 如果是群聊，保存群ID
        group_id = event.get_group_id()
        if group_id:
            session_info['group_id'] = group_id
        
        result = plugin.sicbo_service.start_new_game(game_session_id, session_info)
        
        if result["success"]:
            if plugin.sicbo_service.is_image_mode():
                # 图片模式：生成开庄成功图片
                countdown_seconds = plugin.sicbo_service.get_countdown_seconds()
                image = draw_sicbo_game_start(countdown_seconds)
                image_path = save_image_to_temp(image, "sicbo_start", plugin.data_dir)
                yield event.image_result(image_path)
            else:
                # 文本模式：发送文本消息
                yield event.plain_result(result["message"])
        else:
            # 失败时始终使用文本消息
            yield event.plain_result(result["message"])
    except Exception as e:
        yield event.plain_result(f"❌ 开庄失败：{str(e)}")


async def place_bet(plugin: "FishingPlugin", event: AstrMessageEvent, bet_type: str):
    """下注命令的通用处理函数"""
    game_session_id = event.unified_msg_origin
    user_id = plugin._get_effective_user_id(event)
    args = event.message_str.split(" ")
    
    if len(args) < 2:
        yield event.plain_result(f"❌ 请指定下注金额，例如：/{bet_type} 1000")
        return
    
    amount_str = args[1]
    
    # 支持中文数字
    amount_str = amount_str.replace("万", "0000").replace("千", "000").replace("百", "00")
    
    if not amount_str.isdigit():
        yield event.plain_result("❌ 下注金额必须是数字")
        return
    
    amount = int(amount_str)
    
    try:
        result = plugin.sicbo_service.place_bet(user_id, bet_type, amount, game_session_id)
        
        if result["success"]:
            if plugin.sicbo_service.is_image_mode():
                # 图片模式：生成下注图片
                user = plugin.user_repo.get_by_id(user_id)
                username = user.nickname if user else "未知玩家"
                
                # 根据是否合并选择不同的图片
                if result.get("merged", False):
                    # 合并下注的图片
                    image = draw_sicbo_bet_merged(
                        bet_type, 
                        amount, 
                        result.get("original_amount", 0), 
                        result.get("new_total", 0), 
                        username
                    )
                    image_path = save_image_to_temp(image, "sicbo_bet_merged", plugin.data_dir)
                else:
                    # 普通下注的图片
                    image = draw_sicbo_bet_confirmation(bet_type, amount, username)
                    image_path = save_image_to_temp(image, "sicbo_bet", plugin.data_dir)
                
                yield event.image_result(image_path)
            else:
                # 文本模式：发送文本消息
                yield event.plain_result(result["message"])
        else:
            # 失败时始终使用文本消息
            yield event.plain_result(result["message"])
    except Exception as e:
        yield event.plain_result(f"❌ 下注失败：{str(e)}")


async def bet_big(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭大"""
    async for result in place_bet(plugin, event, "大"):
        yield result


async def bet_small(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭小"""
    async for result in place_bet(plugin, event, "小"):
        yield result


async def bet_odd(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭单"""
    async for result in place_bet(plugin, event, "单"):
        yield result


async def bet_even(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭双"""
    async for result in place_bet(plugin, event, "双"):
        yield result


async def bet_triple(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭豹子"""
    async for result in place_bet(plugin, event, "豹子"):
        yield result


async def bet_one_point(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭一点"""
    async for result in place_bet(plugin, event, "一点"):
        yield result


async def bet_two_point(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭二点"""
    async for result in place_bet(plugin, event, "二点"):
        yield result


async def bet_three_point(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭三点"""
    async for result in place_bet(plugin, event, "三点"):
        yield result


async def bet_four_point(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭四点"""
    async for result in place_bet(plugin, event, "四点"):
        yield result


async def bet_five_point(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭五点"""
    async for result in place_bet(plugin, event, "五点"):
        yield result


async def bet_six_point(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭六点"""
    async for result in place_bet(plugin, event, "六点"):
        yield result


async def bet_total_points(plugin: "FishingPlugin", event: AstrMessageEvent, points: str):
    """鸭总点数的通用函数"""
    async for result in place_bet(plugin, event, f"{points}点"):
        yield result


async def bet_4_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭4点"""
    async for result in bet_total_points(plugin, event, "4"):
        yield result


async def bet_5_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭5点"""
    async for result in bet_total_points(plugin, event, "5"):
        yield result


async def bet_6_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭6点"""
    async for result in bet_total_points(plugin, event, "6"):
        yield result


async def bet_7_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭7点"""
    async for result in bet_total_points(plugin, event, "7"):
        yield result


async def bet_8_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭8点"""
    async for result in bet_total_points(plugin, event, "8"):
        yield result


async def bet_9_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭9点"""
    async for result in bet_total_points(plugin, event, "9"):
        yield result


async def bet_10_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭10点"""
    async for result in bet_total_points(plugin, event, "10"):
        yield result


async def bet_11_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭11点"""
    async for result in bet_total_points(plugin, event, "11"):
        yield result


async def bet_12_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭12点"""
    async for result in bet_total_points(plugin, event, "12"):
        yield result


async def bet_13_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭13点"""
    async for result in bet_total_points(plugin, event, "13"):
        yield result


async def bet_14_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭14点"""
    async for result in bet_total_points(plugin, event, "14"):
        yield result


async def bet_15_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭15点"""
    async for result in bet_total_points(plugin, event, "15"):
        yield result


async def bet_16_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭16点"""
    async for result in bet_total_points(plugin, event, "16"):
        yield result


async def bet_17_points(plugin: "FishingPlugin", event: AstrMessageEvent):
    """鸭17点"""
    async for result in bet_total_points(plugin, event, "17"):
        yield result


async def sicbo_status(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看骰宝游戏状态"""
    try:
        game_session_id = event.unified_msg_origin
        result = plugin.sicbo_service.get_game_status(game_session_id)
        
        if result["success"]:
            if plugin.sicbo_service.is_image_mode():
                # 图片模式：生成状态图片
                game_data = result.get("game_data", {})
                image = draw_sicbo_status(game_data)
                image_path = save_image_to_temp(image, "sicbo_status", plugin.data_dir)
                yield event.image_result(image_path)
            else:
                # 文本模式：生成文本状态消息
                game_data = result.get("game_data", {})
                remaining_time = game_data.get("remaining_time", 0)
                total_bets = game_data.get("total_bets", 0)
                total_amount = game_data.get("total_amount", 0)
                unique_players = game_data.get("unique_players", 0)
                bets = game_data.get("bets", {})
                
                message = f"🎲 骰宝游戏进行中\n"
                message += f"⏰ 剩余时间：{remaining_time} 秒\n"
                message += f"💰 总奖池：{total_amount:,} 金币\n"
                message += f"👥 参与人数：{unique_players} 人\n"
                message += f"📊 总下注：{total_bets} 笔\n\n"
                
                if bets:
                    message += "📋 下注详情：\n"
                    for bet_type, bet_info in bets.items():
                        count = bet_info.get('count', 0)
                        amount = bet_info.get('amount', 0)
                        if count > 0:
                            message += f"  • {bet_type}：{count} 笔，{amount:,} 金币\n"
                else:
                    message += "💭 暂无下注"
                
                yield event.plain_result(message)
        else:
            yield event.plain_result(result["message"])
    except Exception as e:
        yield event.plain_result(f"❌ 查看状态失败：{str(e)}")


async def my_bets(plugin: "FishingPlugin", event: AstrMessageEvent):
    """查看我的下注"""
    game_session_id = event.unified_msg_origin
    user_id = plugin._get_effective_user_id(event)
    try:
        result = plugin.sicbo_service.get_user_bets(user_id, game_session_id)
        
        if result["success"]:
            user = plugin.user_repo.get_by_id(user_id)
            username = user.nickname if user else "未知玩家"
            
            if plugin.sicbo_service.is_image_mode():
                # 图片模式：生成用户下注图片
                user_bets = result.get("bets", [])
                image = draw_sicbo_user_bets(user_bets, username)
                image_path = save_image_to_temp(image, "sicbo_user_bets", plugin.data_dir)
                yield event.image_result(image_path)
            else:
                # 文本模式：生成文本下注消息
                user_bets = result.get("bets", [])
                total_bet = result.get("total_bet", 0)
                
                if user_bets:
                    message = f"📋 {username} 的下注情况：\n\n"
                    for i, bet in enumerate(user_bets, 1):
                        bet_type = bet.get('bet_type', '未知')
                        amount = bet.get('amount', 0)
                        odds = bet.get('odds', 0)
                        message += f"{i}. {bet_type}：{amount:,} 金币 (1:{odds})\n"
                    message += f"\n💰 总下注：{total_bet:,} 金币"
                else:
                    message = f"💭 {username} 还没有下注"
                
                yield event.plain_result(message)
        else:
            yield event.plain_result(result["message"])
    except Exception as e:
        yield event.plain_result(f"❌ 查看下注失败：{str(e)}")


async def sicbo_help(plugin: "FishingPlugin", event: AstrMessageEvent):
    """骰宝游戏帮助"""
    try:
        if plugin.sicbo_service.is_image_mode():
            # 图片模式：生成帮助图片
            countdown_seconds = plugin.sicbo_service.get_countdown_seconds()
            image = draw_sicbo_help(countdown_seconds)
            image_path = save_image_to_temp(image, "sicbo_help", plugin.data_dir)
            yield event.image_result(image_path)
        else:
            # 文本模式：发送简化的帮助文本
            help_message = f"""🎲 骰宝游戏帮助

【游戏流程】
1. 管理员或玩家发送 "/开庄" 开启新游戏
2. 游戏倒计时{plugin.sicbo_service.get_countdown_seconds()}秒，期间玩家可自由下注
3. 倒计时结束后自动开奖并结算

【下注类型】
🎯 大小单双：/鸭大 金额、/鸭小 金额、/鸭单 金额、/鸭双 金额
🐅 豹子：/鸭豹子 金额 (三个骰子相同)
🎲 指定点数：/鸭一点 金额、/鸭二点 金额 ... /鸭六点 金额
📊 总点数：/鸭4点 金额、/鸭5点 金额 ... /鸭17点 金额

【其他命令】
• /骰宝状态 - 查看当前游戏状态
• /我的下注 - 查看本局下注情况
• /骰宝赔率 - 查看详细赔率表
• /骰宝倒计时 [秒数] - 管理员设置倒计时时间

【特殊规则】
⚠️ 豹子杀大小：出现豹子时，大小单双全输
💰 支持中文数字：如 "10万" = "100000"

祝您好运！🍀"""
            yield event.plain_result(help_message)
    except Exception as e:
        yield event.plain_result(f"❌ 获取帮助失败：{str(e)}")


async def sicbo_odds(plugin: "FishingPlugin", event: AstrMessageEvent):
    """骰宝赔率详情"""
    try:
        if plugin.sicbo_service.is_image_mode():
            # 图片模式：生成赔率图片
            image = draw_sicbo_odds()
            image_path = save_image_to_temp(image, "sicbo_odds", plugin.data_dir)
            yield event.image_result(image_path)
        else:
            # 文本模式：发送详细赔率文本
            odds_message = """💰 骰宝赔率详情

【大小单双 1:1】
• 鸭大(11-17点) • 鸭小(4-10点) • 鸭单(奇数) • 鸭双(偶数)

【豹子 1:24】
• 鸭豹子：三个骰子相同

【指定点数 动态赔率】
• 鸭一/二/三/四/五/六点：
  出现1个→1:1 | 出现2个→1:2 | 出现3个→1:3

【总点数赔率表】
4点→1:50   5点→1:18   6点→1:14   7点→1:12
8点→1:8    9点→1:6    10点→1:6
11点→1:6   12点→1:6   13点→1:8
14点→1:12  15点→1:14  16点→1:18  17点→1:50

【重要提醒】
⚠️ 豹子杀大小：出现豹子时大小单双全输
💰 赔率为净赔率，不含本金"""
            yield event.plain_result(odds_message)
    except Exception as e:
        yield event.plain_result(f"❌ 获取赔率失败：{str(e)}")


async def force_settle_sicbo(plugin: "FishingPlugin", event: AstrMessageEvent):
    """管理员强制结算骰宝游戏"""
    try:
        game_session_id = event.unified_msg_origin
        result = await plugin.sicbo_service.force_settle_game(game_session_id)
        yield event.plain_result(result["message"])
    except Exception as e:
        yield event.plain_result(f"❌ 强制结算失败：{str(e)}")


async def set_sicbo_countdown(plugin: "FishingPlugin", event: AstrMessageEvent):
    """[管理员] 设置骰宝倒计时时间"""
    args = event.message_str.split(" ")
    
    if len(args) < 2:
        current_time = plugin.sicbo_service.get_countdown_seconds()
        yield event.plain_result(f"🕐 当前骰宝倒计时设置为 {current_time} 秒\n用法：/骰宝倒计时 <秒数>")
        return
    
    try:
        seconds = int(args[1])
        result = plugin.sicbo_service.set_countdown_seconds(seconds)
        
        if result["success"]:
            # 获取管理员信息
            user_id = plugin._get_effective_user_id(event)
            user = plugin.user_repo.get_by_id(user_id)
            admin_name = user.nickname if user else "管理员"
            
            # 生成设置成功图片
            image = draw_sicbo_countdown_setting(seconds, admin_name)
            image_path = save_image_to_temp(image, "sicbo_countdown_setting", plugin.data_dir)
            yield event.image_result(image_path)
        else:
            yield event.plain_result(result["message"])
    except ValueError:
        yield event.plain_result("❌ 请输入有效的数字")
    except Exception as e:
        yield event.plain_result(f"❌ 设置失败：{str(e)}")


async def set_sicbo_mode(plugin: "FishingPlugin", event: AstrMessageEvent):
    """[管理员] 设置骰宝消息模式"""
    args = event.message_str.split(" ")
    
    if len(args) < 2:
        current_mode = plugin.sicbo_service.get_message_mode()
        mode_name = "图片模式" if current_mode == "image" else "文本模式"
        yield event.plain_result(f"📱 当前骰宝消息模式：{mode_name}\n用法：/骰宝模式 <image|text>")
        return
    
    try:
        mode = args[1].lower()
        
        # 支持中文输入
        if mode in ["图片", "图片模式", "img"]:
            mode = "image"
        elif mode in ["文本", "文字", "文本模式", "txt"]:
            mode = "text"
        
        result = plugin.sicbo_service.set_message_mode(mode)
        
        if result["success"]:
            # 无论什么模式，设置成功都用文本消息反馈
            yield event.plain_result(result["message"])
        else:
            yield event.plain_result(result["message"])
    except Exception as e:
        yield event.plain_result(f"❌ 设置失败：{str(e)}")