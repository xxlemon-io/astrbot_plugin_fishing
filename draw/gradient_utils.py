"""
渐变背景生成工具函数
使用numpy加速渐变生成，提供统一的渐变背景接口
"""
from PIL import Image
from typing import Tuple


def create_vertical_gradient(width: int, height: int, top_color: Tuple[int, int, int], bottom_color: Tuple[int, int, int]) -> Image.Image:
    """
    创建垂直渐变背景，使用numpy加速
    
    Args:
        width: 图像宽度
        height: 图像高度
        top_color: 顶部颜色 (R, G, B)
        bottom_color: 底部颜色 (R, G, B)
    
    Returns:
        PIL.Image.Image: 生成的渐变图像
    """
    try:
        import numpy as np
        # 使用numpy加速渐变生成
        top_r, top_g, top_b = top_color
        bot_r, bot_g, bot_b = bottom_color
        
        # 生成渐变
        y_coords = np.linspace(0, 1, height)
        r_gradient = (top_r + (bot_r - top_r) * y_coords).astype(np.uint8)
        g_gradient = (top_g + (bot_g - top_g) * y_coords).astype(np.uint8)
        b_gradient = (top_b + (bot_b - top_b) * y_coords).astype(np.uint8)
        
        # 创建图像
        gradient_array = np.zeros((height, width, 3), dtype=np.uint8)
        gradient_array[:, :, 0] = r_gradient[:, np.newaxis]
        gradient_array[:, :, 1] = g_gradient[:, np.newaxis]
        gradient_array[:, :, 2] = b_gradient[:, np.newaxis]
        
        return Image.fromarray(gradient_array)
    except ImportError:
        # 回退到原方法
        return _create_vertical_gradient_fallback(width, height, top_color, bottom_color)


def _create_vertical_gradient_fallback(width: int, height: int, top_color: Tuple[int, int, int], bottom_color: Tuple[int, int, int]) -> Image.Image:
    """
    回退的渐变生成方法，当numpy不可用时使用
    """
    from PIL import ImageDraw
    
    base = Image.new('RGB', (width, height), top_color)
    top_r, top_g, top_b = top_color
    bot_r, bot_g, bot_b = bottom_color
    draw = ImageDraw.Draw(base)
    
    # 减少绘制频率以提高性能
    step = max(1, height // 200)  # 最多绘制200行
    for y in range(0, height, step):
        ratio = y / (height - 1)
        r = int(top_r + (bot_r - top_r) * ratio)
        g = int(top_g + (bot_g - top_g) * ratio)
        b = int(top_b + (bot_b - top_b) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    return base


def create_horizontal_gradient(width: int, height: int, left_color: Tuple[int, int, int], right_color: Tuple[int, int, int]) -> Image.Image:
    """
    创建水平渐变背景，使用numpy加速
    
    Args:
        width: 图像宽度
        height: 图像高度
        left_color: 左侧颜色 (R, G, B)
        right_color: 右侧颜色 (R, G, B)
    
    Returns:
        PIL.Image.Image: 生成的渐变图像
    """
    try:
        import numpy as np
        # 使用numpy加速渐变生成
        left_r, left_g, left_b = left_color
        right_r, right_g, right_b = right_color
        
        # 生成渐变
        x_coords = np.linspace(0, 1, width)
        r_gradient = (left_r + (right_r - left_r) * x_coords).astype(np.uint8)
        g_gradient = (left_g + (right_g - left_g) * x_coords).astype(np.uint8)
        b_gradient = (left_b + (right_b - left_b) * x_coords).astype(np.uint8)
        
        # 创建图像
        gradient_array = np.zeros((height, width, 3), dtype=np.uint8)
        gradient_array[:, :, 0] = r_gradient
        gradient_array[:, :, 1] = g_gradient
        gradient_array[:, :, 2] = b_gradient
        
        return Image.fromarray(gradient_array)
    except ImportError:
        # 回退到原方法
        return _create_horizontal_gradient_fallback(width, height, left_color, right_color)


def _create_horizontal_gradient_fallback(width: int, height: int, left_color: Tuple[int, int, int], right_color: Tuple[int, int, int]) -> Image.Image:
    """
    回退的水平渐变生成方法
    """
    from PIL import ImageDraw
    
    base = Image.new('RGB', (width, height), left_color)
    left_r, left_g, left_b = left_color
    right_r, right_g, right_b = right_color
    draw = ImageDraw.Draw(base)
    
    # 减少绘制频率以提高性能
    step = max(1, width // 200)  # 最多绘制200列
    for x in range(0, width, step):
        ratio = x / (width - 1)
        r = int(left_r + (right_r - left_r) * ratio)
        g = int(left_g + (right_g - left_g) * ratio)
        b = int(left_b + (right_b - left_b) * ratio)
        draw.line([(x, 0), (x, height)], fill=(r, g, b))
    
    return base
