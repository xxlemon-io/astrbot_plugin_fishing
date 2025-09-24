"""
文本处理工具函数
优化文本测量、换行和渲染性能
"""
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Optional


def get_text_size_cached(text: str, font: ImageFont.FreeTypeFont, cache: dict = None) -> Tuple[int, int]:
    """
    带缓存的文本尺寸测量，避免重复计算
    
    Args:
        text: 要测量的文本
        font: 字体对象
        cache: 可选的缓存字典
    
    Returns:
        (width, height): 文本尺寸
    """
    if cache is None:
        # 如果没有提供缓存，直接测量
        return _measure_text_size(text, font)
    
    # 使用缓存
    cache_key = f"{text}_{font.size}"
    if cache_key not in cache:
        cache[cache_key] = _measure_text_size(text, font)
    
    return cache[cache_key]


def _measure_text_size(text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    """
    测量文本尺寸的内部函数
    """
    # 创建临时图像进行测量
    temp_img = Image.new('RGB', (1, 1), (255, 255, 255))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text_by_width_optimized(text: str, font: ImageFont.FreeTypeFont, max_width: int, cache: dict = None) -> List[str]:
    """
    优化的文本按宽度换行函数
    
    Args:
        text: 要换行的文本
        font: 字体对象
        max_width: 最大宽度
        cache: 可选的缓存字典
    
    Returns:
        List[str]: 换行后的文本行列表
    """
    if not text:
        return []
    
    # 如果文本很短，直接返回
    text_width, _ = get_text_size_cached(text, font, cache)
    if text_width <= max_width:
        return [text]
    
    lines = []
    current_line = ""
    
    # 按字符分割，但优化测量频率
    for char in text:
        test_line = current_line + char
        test_width, _ = get_text_size_cached(test_line, font, cache)
        
        if test_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = char
    
    if current_line:
        lines.append(current_line)
    
    return lines


def wrap_text_by_width_with_hyphenation(text: str, font: ImageFont.FreeTypeFont, max_width: int, cache: dict = None) -> List[str]:
    """
    带连字符的文本换行，适用于英文文本
    
    Args:
        text: 要换行的文本
        font: 字体对象
        max_width: 最大宽度
        cache: 可选的缓存字典
    
    Returns:
        List[str]: 换行后的文本行列表
    """
    if not text:
        return []
    
    # 先尝试简单换行
    lines = wrap_text_by_width_optimized(text, font, max_width, cache)
    
    # 如果只有一行，直接返回
    if len(lines) <= 1:
        return lines
    
    # 对每行进行连字符优化
    optimized_lines = []
    for line in lines:
        if len(line) > 10 and ' ' in line:  # 只对较长的行进行连字符处理
            words = line.split(' ')
            if len(words) > 1:
                # 尝试在单词边界换行
                current_line = ""
                for word in words:
                    test_line = current_line + (" " if current_line else "") + word
                    test_width, _ = get_text_size_cached(test_line, font, cache)
                    
                    if test_width <= max_width:
                        current_line = test_line
                    else:
                        if current_line:
                            optimized_lines.append(current_line)
                        current_line = word
                
                if current_line:
                    optimized_lines.append(current_line)
            else:
                optimized_lines.append(line)
        else:
            optimized_lines.append(line)
    
    return optimized_lines


def create_text_cache() -> dict:
    """
    创建文本测量缓存
    
    Returns:
        dict: 空的缓存字典
    """
    return {}


def clear_text_cache(cache: dict) -> None:
    """
    清空文本测量缓存
    
    Args:
        cache: 要清空的缓存字典
    """
    cache.clear()


def get_text_metrics_batch(texts: List[str], font: ImageFont.FreeTypeFont, cache: dict = None) -> List[Tuple[int, int]]:
    """
    批量测量文本尺寸，提高效率
    
    Args:
        texts: 文本列表
        font: 字体对象
        cache: 可选的缓存字典
    
    Returns:
        List[Tuple[int, int]]: 每个文本的尺寸列表
    """
    if cache is None:
        return [_measure_text_size(text, font) for text in texts]
    
    results = []
    for text in texts:
        results.append(get_text_size_cached(text, font, cache))
    
    return results
