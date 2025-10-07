import random
import string
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from astrbot.api import logger


class AuthService:
    """认证服务，处理QQ验证码登录"""
    
    def __init__(self):
        # 验证码存储: {qq_id: {code, expires_at, attempts, locked_until}}
        self._verification_codes: Dict[str, Dict] = {}
        # 发送限制: {qq_id: last_send_time}
        self._send_limits: Dict[str, datetime] = {}
        
    def generate_verification_code(self) -> str:
        """生成6位数字验证码"""
        return ''.join(random.choices(string.digits, k=6))
    
    def can_send_code(self, qq_id: str) -> Tuple[bool, str]:
        """检查是否可以发送验证码"""
        now = datetime.now()
        logger.info(f"检查发送频率限制 - QQ: {qq_id}, 当前时间: {now}")
        
        # 检查发送频率限制（5分钟内只能发送1次）
        if qq_id in self._send_limits:
            last_send = self._send_limits[qq_id]
            logger.info(f"上次发送时间 - QQ: {qq_id}, 上次发送: {last_send}, 时间差: {now - last_send}")
            if now - last_send < timedelta(minutes=5):
                remaining = 5 - int((now - last_send).total_seconds() / 60)
                logger.warning(f"频率限制触发 - QQ: {qq_id}, 剩余等待时间: {remaining} 分钟")
                return False, f"请等待 {remaining} 分钟后再试"
        
        # 检查是否被锁定
        if qq_id in self._verification_codes:
            code_info = self._verification_codes[qq_id]
            if 'locked_until' in code_info and code_info['locked_until'] > now:
                remaining = int((code_info['locked_until'] - now).total_seconds() / 60)
                return False, f"验证失败次数过多，请等待 {remaining} 分钟后再试"
        
        return True, ""
    
    def send_verification_code(self, qq_id: str, plugin_instance, skip_rate_limit: bool = False) -> Tuple[bool, str]:
        """发送验证码到QQ"""
        logger.info(f"发送验证码请求 - QQ: {qq_id}, skip_rate_limit: {skip_rate_limit}")
        
        # 如果跳过频率限制（比如在私聊中），则只检查锁定状态
        if skip_rate_limit:
            logger.info(f"跳过频率限制检查 - QQ: {qq_id}")
            # 只检查是否被锁定，不检查发送频率
            if qq_id in self._verification_codes:
                code_info = self._verification_codes[qq_id]
                if 'locked_until' in code_info and code_info['locked_until'] > datetime.now():
                    remaining = int((code_info['locked_until'] - datetime.now()).total_seconds() / 60)
                    return False, f"验证失败次数过多，请等待 {remaining} 分钟后再试"
        else:
            can_send, error_msg = self.can_send_code(qq_id)
            if not can_send:
                return False, error_msg
        
        # 生成验证码
        code = self.generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=5)
        
        # 存储验证码信息
        self._verification_codes[qq_id] = {
            'code': code,
            'expires_at': expires_at,
            'attempts': 0
        }
        
        # 调试日志
        logger.info(f"验证码已存储 - QQ: {qq_id}, 验证码: {code}, 过期时间: {expires_at}")
        logger.info(f"存储后验证码数量: {len(self._verification_codes)}")
        logger.info(f"存储后验证码QQ号: {list(self._verification_codes.keys())}")
        
        # 更新发送限制
        self._send_limits[qq_id] = datetime.now()
        
        # 通过Bot发送消息
        try:
            message = f"【钓鱼游戏】您的验证码是：{code}，5分钟内有效。"
            
            # 使用现有的消息服务发送验证码
            if plugin_instance and hasattr(plugin_instance, 'message_service'):
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    success = loop.run_until_complete(plugin_instance.message_service.send_private_message(
                        user_id=qq_id,
                        message=message
                    ))
                    if success:
                        logger.info(f"验证码已通过消息服务发送到 QQ {qq_id}")
                        return True, "验证码已发送"
                    else:
                        logger.warning(f"消息服务发送失败，验证码: {code}")
                        return True, f"您的验证码是：{code}，5分钟内有效"
                except Exception as e:
                    logger.debug(f"消息服务发送失败: {e}")
            
            # 备用方案：直接通过bot发送
            if plugin_instance and hasattr(plugin_instance, 'bot') and hasattr(plugin_instance.bot, 'call_action'):
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    loop.create_task(plugin_instance.bot.call_action(
                        "send_private_msg",
                        user_id=int(qq_id),
                        message=message
                    ))
                    logger.info(f"验证码已通过 bot.call_action 发送到 QQ {qq_id}")
                    return True, "验证码已发送"
                except Exception as e:
                    logger.debug(f"bot.call_action发送失败: {e}")
            
            # 如果所有方式都失败，记录日志并返回验证码
            logger.warning(f"所有发送方式都失败，验证码: {code}")
            return True, f"您的验证码是：{code}，5分钟内有效"
            
        except Exception as e:
            logger.error(f"发送验证码失败: {e}")
            return False, "发送验证码失败，请稍后重试"
    
    def verify_code(self, qq_id: str, input_code: str) -> Tuple[bool, str]:
        """验证验证码"""
        logger.info(f"开始验证验证码 - QQ: {qq_id}, 输入验证码: {input_code}")
        logger.info(f"当前存储的验证码数量: {len(self._verification_codes)}")
        logger.info(f"存储的验证码QQ号: {list(self._verification_codes.keys())}")
        
        if qq_id not in self._verification_codes:
            logger.warning(f"验证码不存在 - QQ: {qq_id}")
            return False, "请先获取验证码"
        
        code_info = self._verification_codes[qq_id]
        now = datetime.now()
        
        logger.info(f"验证码信息 - QQ: {qq_id}, 存储的验证码: {code_info['code']}, 过期时间: {code_info['expires_at']}, 当前时间: {now}")
        
        # 检查是否过期
        if code_info['expires_at'] < now:
            logger.warning(f"验证码已过期 - QQ: {qq_id}, 过期时间: {code_info['expires_at']}, 当前时间: {now}")
            del self._verification_codes[qq_id]
            return False, "验证码已过期，请重新获取"
        
        # 检查是否被锁定
        if 'locked_until' in code_info and code_info['locked_until'] > now:
            remaining = int((code_info['locked_until'] - now).total_seconds() / 60)
            return False, f"验证失败次数过多，请等待 {remaining} 分钟后再试"
        
        # 验证码正确
        if code_info['code'] == input_code:
            # 验证成功，清理验证码
            del self._verification_codes[qq_id]
            return True, "验证成功"
        
        # 验证码错误
        code_info['attempts'] += 1
        
        # 检查失败次数
        if code_info['attempts'] >= 3:
            # 锁定10分钟
            code_info['locked_until'] = now + timedelta(minutes=10)
            return False, "验证失败次数过多，请等待10分钟后再试"
        
        remaining_attempts = 3 - code_info['attempts']
        return False, f"验证码错误，还有 {remaining_attempts} 次机会"
    
    def cleanup_expired_codes(self):
        """清理过期的验证码"""
        now = datetime.now()
        expired_qq_ids = []
        
        for qq_id, code_info in self._verification_codes.items():
            if code_info['expires_at'] < now:
                expired_qq_ids.append(qq_id)
        
        for qq_id in expired_qq_ids:
            del self._verification_codes[qq_id]
        
        # 清理过期的发送限制
        expired_send_limits = []
        for qq_id, last_send in self._send_limits.items():
            if now - last_send > timedelta(hours=1):  # 1小时后清理发送记录
                expired_send_limits.append(qq_id)
        
        for qq_id in expired_send_limits:
            del self._send_limits[qq_id]
