"""
认证相关处理器
处理验证码获取、登录等认证功能
"""
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent


@filter.command("获取验证码", alias={"验证码", "获取码"})
async def get_verification_code(self, event: AstrMessageEvent):
    """获取验证码命令 - 在群组里触发时会通过私聊发送验证码"""
    # 存储用户的消息来源
    self.store_user_message_origin(event)
    
    user_id = event.get_sender_id()
    sender_name = event.get_sender_name() or "未知用户"
    
    # 检查是否在群组中
    group_id = event.get_group_id()
    if group_id:
        # 在群组中，提示将通过私聊发送验证码
        yield event.plain_result(f"@{sender_name} 为了安全起见，验证码将通过私聊发送给您，请查看私聊消息。")
    
    # 调用认证服务发送验证码
    try:
        # 在私聊中跳过频率限制，在群组中保持频率限制
        skip_rate_limit = group_id is None
        logger.info(f"获取验证码命令 - QQ: {user_id}, 群组ID: {group_id}, skip_rate_limit: {skip_rate_limit}")
        success, message = self.auth_service.send_verification_code(user_id, self, skip_rate_limit)
        
        if success:
            if group_id:
                # 在群组中，只显示成功消息
                yield event.plain_result("验证码已发送到您的私聊，请查看私聊消息。")
            else:
                # 在私聊中，显示完整信息
                yield event.plain_result(message)
        else:
            yield event.plain_result(f"获取验证码失败：{message}")
            
    except Exception as e:
        logger.error(f"获取验证码命令执行失败: {e}")
        yield event.plain_result("获取验证码失败，请稍后重试。")


