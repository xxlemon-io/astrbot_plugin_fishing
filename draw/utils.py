import os
from typing import Optional
from PIL import Image, ImageDraw

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
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url, timeout=2) as response:
                    if response.status == 200:
                        content = await response.read()
                        avatar_image = Image.open(BytesIO(content)).convert('RGBA')
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
