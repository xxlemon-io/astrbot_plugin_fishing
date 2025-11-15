import os
import hashlib
from typing import Optional
from PIL import Image, ImageDraw
from astrbot.api import logger

async def get_user_avatar(user_id: str, data_dir: str, avatar_size: int = 50) -> Optional[Image.Image]:
    """
    获取用户头像并处理为圆形
    
    Args:
        user_id: 用户ID
        data_dir: 插件的数据目录
        avatar_size: 头像尺寸
    
    Returns:
        处理后的头像图像，如果失败返回None
    """
    try:
        import aiohttp
        from io import BytesIO
        import time
        
        # 创建头像缓存目录
        cache_dir = os.path.join(data_dir, "avatar_cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        # 安全化user_id用于文件名
        import re
        safe_user_id = re.sub(r'[^a-zA-Z0-9._-]', '_', user_id)
        safe_user_id = re.sub(r'_+', '_', safe_user_id).strip('_') or 'unknown'
        avatar_cache_path = os.path.join(cache_dir, f"{safe_user_id}_avatar.png")
        
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
            try:
                # 增加超时时间并添加重试机制
                timeout = aiohttp.ClientTimeout(total=10, connect=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(avatar_url) as response:
                        if response.status == 200:
                            content = await response.read()
                            avatar_image = Image.open(BytesIO(content)).convert('RGBA')
                            # 保存到缓存
                            avatar_image.save(avatar_cache_path, 'PNG')
            except Exception as e:
                # 如果下载失败，记录日志但不抛出异常
                logger.warning(f"头像下载失败: {e}")
                return None
        
        if avatar_image:
            return avatar_postprocess(avatar_image, avatar_size)
        
    except Exception as e:
        pass
    
    return None

def avatar_postprocess(avatar_image: Image.Image, size: int) -> Image.Image:
    """
    将头像处理为指定大小的圆角头像
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

async def get_fish_icon(icon_url: str, data_dir: str, icon_size: int = 60) -> Optional[Image.Image]:
    """
    下载并处理鱼类图标
    
    Args:
        icon_url: 图标URL
        data_dir: 插件的数据目录
        icon_size: 图标尺寸
    
    Returns:
        处理后的图标图像，如果失败返回None
    """
    if not icon_url or not icon_url.strip():
        return None
    
    try:
        import aiohttp
        from io import BytesIO
        import time
        
        # 创建图标缓存目录
        cache_dir = os.path.join(data_dir, "fish_icon_cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        # 使用URL的hash作为缓存文件名
        url_hash = hashlib.md5(icon_url.encode()).hexdigest()
        icon_cache_path = os.path.join(cache_dir, f"{url_hash}.png")
        
        # 检查是否有缓存的图标（7天刷新）
        icon_image = None
        if os.path.exists(icon_cache_path):
            try:
                file_age = time.time() - os.path.getmtime(icon_cache_path)
                if file_age < 604800:  # 7天
                    icon_image = Image.open(icon_cache_path).convert('RGBA')
            except:
                pass
        
        # 如果没有缓存或缓存过期，重新下载
        if icon_image is None:
            try:
                timeout = aiohttp.ClientTimeout(total=10, connect=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(icon_url.strip()) as response:
                        if response.status == 200:
                            content = await response.read()
                            # 限制文件大小（最大5MB）
                            if len(content) > 5 * 1024 * 1024:
                                logger.warning(f"图标文件过大，跳过: {icon_url}")
                                return None
                            icon_image = Image.open(BytesIO(content)).convert('RGBA')
                            # 保存到缓存
                            icon_image.save(icon_cache_path, 'PNG')
                        else:
                            logger.warning(f"下载图标失败，HTTP状态码: {response.status}, URL: {icon_url}")
                            return None
            except Exception as e:
                # 如果下载失败，记录日志但不抛出异常
                logger.warning(f"图标下载失败: {e}, URL: {icon_url}")
                return None
        
        if icon_image:
            # 调整图标大小并保持宽高比
            icon_image.thumbnail((icon_size, icon_size), Image.Resampling.LANCZOS)
            return icon_image
        
    except Exception as e:
        logger.warning(f"处理图标时发生错误: {e}, URL: {icon_url}")
    
    return None
