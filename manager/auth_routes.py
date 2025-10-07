import asyncio
import functools
from datetime import datetime, timedelta
from quart import Blueprint, render_template, request, session, jsonify, current_app
from astrbot.api import logger

from ..core.services.auth_service import AuthService

# 创建认证相关的Blueprint
auth_bp = Blueprint("auth_bp", __name__)

# 全局认证服务实例
auth_service = AuthService()


def auth_login_required(f):
    """游戏登录验证装饰器"""
    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        if "game_user_id" not in session:
            return jsonify({"success": False, "message": "请先登录", "redirect": "/game/login"}), 401
        return await f(*args, **kwargs)
    return wrapper


@auth_bp.route("/game/login", methods=["GET"])
async def auth_login_page():
    """游戏登录页面"""
    return await render_template("game/login.html")


@auth_bp.route("/game/api/send-code", methods=["POST"])
async def send_verification_code():
    """发送验证码"""
    try:
        data = await request.get_json()
        qq_id = data.get("qq_id", "").strip()
        
        if not qq_id or not qq_id.isdigit():
            return jsonify({"success": False, "message": "请输入有效的QQ号"})
        
        # 检查是否可以发送验证码
        can_send, error_msg = auth_service.can_send_code(qq_id)
        if not can_send:
            return jsonify({"success": False, "message": error_msg})
        
        # 生成验证码
        code = auth_service.generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=5)
        
        # 存储验证码信息
        auth_service._verification_codes[qq_id] = {
            'code': code,
            'expires_at': expires_at,
            'attempts': 0
        }
        
        # 更新发送限制
        auth_service._send_limits[qq_id] = datetime.now()
        
        # 1. 日志记录（方便测试）
        logger.info(f"========================================")
        logger.info(f"验证码已生成 - QQ: {qq_id}")
        logger.info(f"验证码: {code}")
        logger.info(f"有效期: 5分钟")
        logger.info(f"========================================")
        
        # 2. 通过Bot发送私聊消息
        plugin_instance = current_app.config.get("PLUGIN_INSTANCE")
        if plugin_instance:
            try:
                # 构造消息内容
                message = f"【钓鱼游戏】您的验证码是：{code}，5分钟内有效。"
                
                # 使用消息服务发送验证码
                if hasattr(plugin_instance, 'message_service'):
                    sent = await plugin_instance.message_service.send_private_message(qq_id, message)
                    if sent:
                        logger.info(f"验证码已通过消息服务发送到 QQ {qq_id}")
                    else:
                        logger.warning("消息服务发送失败，请查看日志获取验证码")
                else:
                    # 备用方案：直接发送
                    sent = False
                    
                    # 方式1: 直接通过插件实例的 bot 属性（最可靠的方式）
                    if hasattr(plugin_instance, 'bot') and hasattr(plugin_instance.bot, 'call_action'):
                        try:
                            await plugin_instance.bot.call_action(
                                "send_private_msg",
                                user_id=int(qq_id),
                                message=message
                            )
                            logger.info(f"验证码已通过 plugin_instance.bot.call_action 发送到 QQ {qq_id}")
                            sent = True
                        except Exception as e:
                            logger.debug(f"bot.call_action方式失败: {e}")
                    
                    # 方式2: 通过 context.get_platform_adapter() 获取平台适配器
                    if not sent and hasattr(plugin_instance.context, 'get_platform_adapter'):
                        try:
                            platform_adapter = plugin_instance.context.get_platform_adapter()
                            if hasattr(platform_adapter, 'bot') and hasattr(platform_adapter.bot, 'call_action'):
                                await platform_adapter.bot.call_action(
                                    "send_private_msg",
                                    user_id=int(qq_id),
                                    message=message
                                )
                                logger.info(f"验证码已通过 platform_adapter.bot.call_action 发送到 QQ {qq_id}")
                                sent = True
                        except Exception as e:
                            logger.debug(f"platform_adapter方式失败: {e}")
                    
                    
                    if not sent:
                        logger.warning("所有发送方式都失败，请查看日志获取验证码")
                    
            except Exception as send_error:
                logger.warning(f"通过Bot发送验证码失败（用户仍可通过日志查看）: {send_error}")
                logger.info(f"验证码已记录在日志中，请查看上方日志获取验证码")
        
        return jsonify({"success": True, "message": "验证码已发送（请查看日志或QQ私聊）"})
            
    except Exception as e:
        logger.error(f"发送验证码API错误: {e}", exc_info=True)
        return jsonify({"success": False, "message": "服务器错误，请稍后重试"})


@auth_bp.route("/game/api/verify-code", methods=["POST"])
async def verify_code():
    """验证验证码并登录"""
    try:
        data = await request.get_json()
        qq_id = data.get("qq_id", "").strip()
        code = data.get("code", "").strip()
        
        if not qq_id or not qq_id.isdigit():
            return jsonify({"success": False, "message": "请输入有效的QQ号"})
        
        if not code or len(code) != 6:
            return jsonify({"success": False, "message": "请输入6位验证码"})
        
        # 验证验证码
        is_valid, message = auth_service.verify_code(qq_id, code)
        if not is_valid:
            return jsonify({"success": False, "message": message})
        
        # 验证成功，检查用户是否存在
        user_service = current_app.config.get("USER_SERVICE")
        if not user_service:
            return jsonify({"success": False, "message": "服务不可用，请稍后重试"})
        
        # 检查用户是否已注册
        user = user_service.user_repo.get_by_id(qq_id)
        if not user:
            # 自动注册用户
            nickname = f"玩家{qq_id[-4:]}"  # 使用QQ号后4位作为默认昵称
            register_result = user_service.register(qq_id, nickname)
            if not register_result:
                return jsonify({"success": False, "message": "注册失败，请稍后重试"})
        
        # 创建游戏会话
        session["game_user_id"] = qq_id
        session["game_logged_in"] = True
        
        # 更新用户最后登录时间
        try:
            user = user_service.user_repo.get_by_id(qq_id)
            if user:
                from ..core.utils import get_now
                user.last_login_time = get_now()
                user_service.user_repo.update(user)
                logger.info(f"用户 {qq_id} 通过WebUI登录成功")
        except Exception as e:
            logger.warning(f"更新用户登录时间失败: {e}")
        
        return jsonify({
            "success": True, 
            "message": "登录成功",
            "redirect": "/game/"
        })
        
    except Exception as e:
        logger.error(f"验证码验证API错误: {e}")
        return jsonify({"success": False, "message": "服务器错误，请稍后重试"})


@auth_bp.route("/game/api/logout", methods=["POST"])
async def auth_logout():
    """退出游戏登录"""
    session.pop("game_user_id", None)
    session.pop("game_logged_in", None)
    return jsonify({"success": True, "message": "已退出登录", "redirect": "/game/login"})


@auth_bp.route("/game/api/check-login", methods=["GET"])
async def check_login_status():
    """检查登录状态"""
    if "game_user_id" in session and session.get("game_logged_in"):
        return jsonify({
            "success": True, 
            "logged_in": True,
            "user_id": session["game_user_id"]
        })
    else:
        return jsonify({
            "success": True,
            "logged_in": False
        })
