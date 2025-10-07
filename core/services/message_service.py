"""
消息发送服务
提供统一的消息发送接口，支持被动和主动消息发送
"""
import asyncio
from typing import Optional, Union, List
from astrbot.api import logger
from astrbot.api.event import MessageChain
import astrbot.api.message_components as Comp


class MessageService:
    """消息发送服务"""
    
    def __init__(self, plugin_instance):
        self.plugin_instance = plugin_instance
        self._unified_msg_origins = {}  # 存储用户的unified_msg_origin
    
    def store_unified_msg_origin(self, user_id: str, unified_msg_origin: str):
        """存储用户的unified_msg_origin，用于主动消息发送"""
        self._unified_msg_origins[user_id] = unified_msg_origin
        logger.debug(f"已存储用户 {user_id} 的 unified_msg_origin")
    
    def get_unified_msg_origin(self, user_id: str) -> Optional[str]:
        """获取用户的unified_msg_origin"""
        return self._unified_msg_origins.get(user_id)
    
    
    
    async def send_private_message(self, user_id: str, message: str, unified_msg_origin: str = None) -> bool:
        """发送私聊消息"""
        try:
            logger.debug(f"开始发送私聊消息到用户 {user_id}")
            
            # 方式1: 使用 event.bot.send_private_msg（最可靠的方式）
            if hasattr(self.plugin_instance, 'bot') and hasattr(self.plugin_instance.bot, 'send_private_msg'):
                logger.debug("尝试使用 bot.send_private_msg 发送消息")
                try:
                    await self.plugin_instance.bot.send_private_msg(
                        user_id=int(user_id),
                        message=message
                    )
                    logger.info(f"私聊消息已通过 bot.send_private_msg 发送到用户 {user_id}")
                    return True
                except Exception as e:
                    logger.debug(f"bot.send_private_msg发送失败: {e}")
            
            # 方式2: 使用 context.send_message（根据实际签名 ['session', 'message_chain']）
            if hasattr(self.plugin_instance.context, 'send_message'):
                logger.debug("尝试使用 context.send_message 发送消息")
                try:
                    from astrbot.api.event import MessageChain
                    
                    # 构建 MessageChain 对象
                    message_chain = MessageChain().message(message)
                    logger.debug(f"MessageChain 对象创建成功: {type(message_chain)}")
                    
                    # 优先使用真实的 unified_msg_origin
                    if unified_msg_origin:
                        try:
                            logger.debug(f"尝试使用真实的 unified_msg_origin: {unified_msg_origin}")
                            await self.plugin_instance.context.send_message(unified_msg_origin, message_chain)
                            logger.info(f"私聊消息已通过 context.send_message 发送到用户 {user_id} (使用真实UMO: {unified_msg_origin})")
                            return True
                        except Exception as e:
                            logger.debug(f"使用真实 UMO {unified_msg_origin} 发送失败: {e}")
                    
                    # 备用方案：尝试不同的 unified_msg_origin 格式（3段式：type:id:sub_id）
                    unified_msg_origins = [
                        f"private:{user_id}:0",
                        f"group:{user_id}:0",
                        f"qq:{user_id}:0",
                        f"aiocqhttp:{user_id}:0",
                        f"private_aiocqhttp_{user_id}_0",
                        f"group_aiocqhttp_{user_id}_0",
                    ]
                    
                    for umo in unified_msg_origins:
                        try:
                            logger.debug(f"尝试使用 unified_msg_origin: {umo}")
                            await self.plugin_instance.context.send_message(umo, message_chain)
                            logger.info(f"私聊消息已通过 context.send_message 发送到用户 {user_id} (使用UMO: {umo})")
                            return True
                        except Exception as e:
                            logger.debug(f"使用 UMO {umo} 发送失败: {e}")
                            continue
                                
                except Exception as e:
                    logger.debug(f"context.send_message 发送失败: {e}")
            
            # 方式3: 直接通过插件实例的 bot 属性（备用方式）
            if hasattr(self.plugin_instance, 'bot') and hasattr(self.plugin_instance.bot, 'call_action'):
                logger.debug("尝试使用 bot.call_action 发送消息")
                try:
                    await self.plugin_instance.bot.call_action(
                        "send_private_msg",
                        user_id=int(user_id),
                        message=message
                    )
                    logger.info(f"私聊消息已通过 bot.call_action 发送到用户 {user_id}")
                    return True
                except Exception as e:
                    logger.debug(f"bot.call_action发送失败: {e}")
            
            # 方式4: 通过 context.get_platform_adapter() 获取平台适配器
            if hasattr(self.plugin_instance.context, 'get_platform_adapter'):
                logger.debug("尝试使用 platform_adapter 发送消息")
                try:
                    platform_adapter = self.plugin_instance.context.get_platform_adapter()
                    if hasattr(platform_adapter, 'bot') and hasattr(platform_adapter.bot, 'call_action'):
                        await platform_adapter.bot.call_action(
                            "send_private_msg",
                            user_id=int(user_id),
                            message=message
                        )
                        logger.info(f"私聊消息已通过 platform_adapter 发送到用户 {user_id}")
                        return True
                except Exception as e:
                    logger.debug(f"platform_adapter发送失败: {e}")
            
            logger.warning(f"所有发送方式都失败，无法发送消息到用户 {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"发送私聊消息失败: {e}")
            return False
    
    async def send_private_message_with_chain(self, user_id: str, message_components: List) -> bool:
        """使用消息链发送私聊消息"""
        try:
            # 方式1: 使用 bot.send_private_msg（最可靠的方式）
            if hasattr(self.plugin_instance, 'bot') and hasattr(self.plugin_instance.bot, 'send_private_msg'):
                try:
                    # 将消息链转换为字符串
                    message_text = self._extract_text_from_components(message_components)
                    
                    await self.plugin_instance.bot.send_private_msg(
                        user_id=int(user_id),
                        message=message_text
                    )
                    logger.info(f"私聊消息链已通过 bot.send_private_msg 发送到用户 {user_id}")
                    return True
                except Exception as e:
                    logger.debug(f"bot.send_private_msg发送失败: {e}")
            
            # 方式2: 使用 context.send_message
            if hasattr(self.plugin_instance.context, 'send_message'):
                try:
                    from astrbot.api.event import MessageChain
                    
                    # 构建 MessageChain 对象
                    message_chain = MessageChain()
                    for component in message_components:
                        message_chain = message_chain.add(component)
                    
                    # 尝试不同的 unified_msg_origin 格式（3段式：type:id:sub_id）
                    unified_msg_origins = [
                        f"private:{user_id}:0",
                        f"group:{user_id}:0",
                        f"qq:{user_id}:0",
                        f"aiocqhttp:{user_id}:0",
                        f"private_aiocqhttp_{user_id}_0",
                        f"group_aiocqhttp_{user_id}_0",
                    ]
                    
                    for umo in unified_msg_origins:
                        try:
                            await self.plugin_instance.context.send_message(umo, message_chain)
                            logger.info(f"富媒体私聊消息已通过 MessageChain 发送到用户 {user_id} (使用UMO: {umo})")
                            return True
                        except Exception as e:
                            logger.debug(f"使用 UMO {umo} 发送富媒体消息失败: {e}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"MessageChain富媒体发送失败: {e}")
            
            # 备用方案：转换为纯文本发送
            text_message = self._extract_text_from_components(message_components)
            return await self.send_private_message(user_id, text_message)
            
        except Exception as e:
            logger.error(f"发送富媒体私聊消息失败: {e}")
            return False
    
    def _extract_text_from_components(self, components: List) -> str:
        """从消息组件中提取纯文本"""
        text_parts = []
        for component in components:
            if hasattr(component, 'text'):
                text_parts.append(component.text)
            elif hasattr(component, 'message'):
                text_parts.append(component.message)
            elif isinstance(component, str):
                text_parts.append(component)
        return "".join(text_parts)
    
    async def send_forward_message(self, user_id: str, forward_nodes: List) -> bool:
        """发送群合并转发消息"""
        try:
            if hasattr(self.plugin_instance.context, 'send_message'):
                try:
                    from astrbot.api.event import MessageChain
                    
                    # 构建 MessageChain 对象
                    message_chain = MessageChain()
                    for node in forward_nodes:
                        message_chain = message_chain.add(node)
                    
                    # 尝试不同的 unified_msg_origin 格式（3段式：type:id:sub_id）
                    unified_msg_origins = [
                        f"private:{user_id}:0",
                        f"group:{user_id}:0",
                        f"qq:{user_id}:0",
                        f"aiocqhttp:{user_id}:0",
                        f"private_aiocqhttp_{user_id}_0",
                        f"group_aiocqhttp_{user_id}_0",
                    ]
                    
                    for umo in unified_msg_origins:
                        try:
                            await self.plugin_instance.context.send_message(umo, message_chain)
                            logger.info(f"转发消息已通过 MessageChain 发送到用户 {user_id} (使用UMO: {umo})")
                            return True
                        except Exception as e:
                            logger.debug(f"使用 UMO {umo} 发送转发消息失败: {e}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"转发消息发送失败: {e}")
            
            # 备用方案：转换为普通消息
            return await self.send_private_message(user_id, "转发消息发送失败，已转换为普通消息")
            
        except Exception as e:
            logger.error(f"发送转发消息失败: {e}")
            return False
    
    def create_forward_node(self, uin: int, name: str, content: List) -> object:
        """创建转发消息节点"""
        try:
            from astrbot.api.message_components import Node
            return Node(uin=uin, name=name, content=content)
        except ImportError:
            logger.warning("无法导入 Node 组件，转发消息功能不可用")
            return None
    
    async def send_active_message(self, user_id: str, message: str) -> bool:
        """发送主动消息（使用存储的unified_msg_origin）"""
        unified_msg_origin = self.get_unified_msg_origin(user_id)
        if not unified_msg_origin:
            logger.warning(f"用户 {user_id} 的 unified_msg_origin 未存储，无法发送主动消息")
            return False
        
        try:
            if hasattr(self.plugin_instance.context, 'send_message'):
                try:
                    from astrbot.api.event import MessageChain
                    
                    # 构建 MessageChain 对象
                    message_chain = MessageChain().message(message)
                    
                    # 发送主动消息（使用存储的 unified_msg_origin 作为 session）
                    await self.plugin_instance.context.send_message(unified_msg_origin, message_chain)
                    logger.info(f"主动消息已通过 MessageChain 发送到用户 {user_id}")
                    return True
                except Exception as e:
                    logger.debug(f"主动消息MessageChain发送失败: {e}")
            
            # 备用方案：使用私聊消息
            return await self.send_private_message(user_id, message)
            
        except Exception as e:
            logger.error(f"发送主动消息失败: {e}")
            return False
    
    async def send_active_message_with_chain(self, user_id: str, message_components: List) -> bool:
        """使用消息链发送主动消息"""
        unified_msg_origin = self.get_unified_msg_origin(user_id)
        if not unified_msg_origin:
            logger.warning(f"用户 {user_id} 的 unified_msg_origin 未存储，无法发送主动消息")
            return False
        
        try:
            if hasattr(self.plugin_instance.context, 'send_message'):
                try:
                    from astrbot.api.event import MessageChain
                    
                    # 构建 MessageChain 对象
                    message_chain = MessageChain()
                    for component in message_components:
                        message_chain = message_chain.add(component)
                    
                    # 发送主动消息（使用存储的 unified_msg_origin 作为 session）
                    await self.plugin_instance.context.send_message(unified_msg_origin, message_chain)
                    logger.info(f"富媒体主动消息已通过 MessageChain 发送到用户 {user_id}")
                    return True
                except Exception as e:
                    logger.debug(f"主动消息MessageChain富媒体发送失败: {e}")
            
            # 备用方案：使用私聊消息
            return await self.send_private_message_with_chain(user_id, message_components)
            
        except Exception as e:
            logger.error(f"发送富媒体主动消息失败: {e}")
            return False
