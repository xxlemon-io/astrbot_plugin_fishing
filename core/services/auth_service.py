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
        
        # 检查发送频率限制（5分钟内只能发送1次）
        if qq_id in self._send_limits:
            last_send = self._send_limits[qq_id]
            if now - last_send < timedelta(minutes=5):
                remaining = 5 - int((now - last_send).total_seconds() / 60)
                return False, f"请等待 {remaining} 分钟后再试"
        
        # 检查是否被锁定
        if qq_id in self._verification_codes:
            code_info = self._verification_codes[qq_id]
            if 'locked_until' in code_info and code_info['locked_until'] > now:
                remaining = int((code_info['locked_until'] - now).total_seconds() / 60)
                return False, f"验证失败次数过多，请等待 {remaining} 分钟后再试"
        
        return True, ""
    
    def send_verification_code(self, qq_id: str, bot_instance) -> Tuple[bool, str]:
        """发送验证码到QQ"""
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
        
        # 更新发送限制
        self._send_limits[qq_id] = datetime.now()
        
        # 通过Bot发送消息
        try:
            message = f"【钓鱼游戏】您的验证码是：{code}，5分钟内有效。"
            # 这里需要调用Bot的消息发送功能
            # 由于AstrBot的API限制，我们需要通过插件实例来发送
            # 暂时记录日志，实际发送需要在路由中处理
            logger.info(f"验证码发送到QQ {qq_id}: {code}")
            
            # TODO: 实际的消息发送需要通过bot_instance实现
            # 这里先返回成功，实际发送在路由中处理
            
            return True, "验证码已发送"
        except Exception as e:
            logger.error(f"发送验证码失败: {e}")
            return False, "发送验证码失败，请稍后重试"
    
    def verify_code(self, qq_id: str, input_code: str) -> Tuple[bool, str]:
        """验证验证码"""
        if qq_id not in self._verification_codes:
            return False, "请先获取验证码"
        
        code_info = self._verification_codes[qq_id]
        now = datetime.now()
        
        # 检查是否过期
        if code_info['expires_at'] < now:
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
