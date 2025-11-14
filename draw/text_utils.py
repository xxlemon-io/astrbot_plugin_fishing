"""
文本处理工具函数
优化文本测量、换行和渲染性能
"""
import os
import platform
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


def _find_cjk_font() -> Optional[str]:
    """
    查找CJK字体路径（支持繁体中文字符）
    
    Returns:
        字体文件路径，如果找不到则返回None
    """
    resource_dir = os.path.join(os.path.dirname(__file__), "resource")
    
    # 使用项目资源目录中的字体（按优先级排序）
    cjk_fonts = [
        "NotoSansTC-Bold.ttf",  # Noto Sans 繁体中文（优先）
        "NotoSansJP-Bold.ttf",  # Noto Sans 日文（后备）
    ]
    
    for font_name in cjk_fonts:
        font_path = os.path.join(resource_dir, font_name)
        if os.path.exists(font_path):
            return font_path
    
    return None


class FontWithFallback:
    """
    带自动回退的字体包装类
    当主字体不支持某个字符时，自动使用系统CJK字体
    """
    def __init__(self, primary_font: ImageFont.FreeTypeFont, fallback_font: Optional[ImageFont.FreeTypeFont] = None):
        self.primary_font = primary_font
        self.fallback_font = fallback_font
        self._char_cache = {}  # 缓存字符到字体的映射
    
    def _is_cjk_char(self, char: str) -> bool:
        """判断是否为CJK字符（中文、日文、韩文）"""
        if not char:
            return False
        code = ord(char)
        # CJK统一汉字、CJK扩展A/B/C/D/E、CJK兼容汉字、日文平假名/片假名、韩文等
        return (
            0x4E00 <= code <= 0x9FFF or  # CJK统一汉字
            0x3400 <= code <= 0x4DBF or  # CJK扩展A
            0x20000 <= code <= 0x2A6DF or  # CJK扩展B
            0x2A700 <= code <= 0x2B73F or  # CJK扩展C
            0x2B740 <= code <= 0x2B81F or  # CJK扩展D
            0x2B820 <= code <= 0x2CEAF or  # CJK扩展E
            0xF900 <= code <= 0xFAFF or  # CJK兼容汉字
            0x3040 <= code <= 0x309F or  # 日文平假名
            0x30A0 <= code <= 0x30FF or  # 日文片假名
            0xAC00 <= code <= 0xD7AF     # 韩文音节
        )
    
    def _get_font_for_char(self, char: str) -> ImageFont.FreeTypeFont:
        """获取适合该字符的字体"""
        if char in self._char_cache:
            return self._char_cache[char]
        
        # 对于CJK字符，如果有回退字体，直接使用回退字体以确保正确显示
        # 这样可以避免主字体可能将繁体字映射到其他字符的问题
        if self.fallback_font and self._is_cjk_char(char):
            self._char_cache[char] = self.fallback_font
            return self.fallback_font
        
        # 非CJK字符或没有回退字体，使用主字体
        self._char_cache[char] = self.primary_font
        return self.primary_font
    
    def getmask(self, text, mode="", *args, **kwargs):
        """获取文本的mask，自动处理回退"""
        if not self.fallback_font or len(text) == 1:
            return self.primary_font.getmask(text, mode, *args, **kwargs)
        
        # 对于多字符文本，需要逐个字符处理
        # 这里简化处理：如果回退字体存在，尝试使用它
        try:
            return self.primary_font.getmask(text, mode, *args, **kwargs)
        except Exception:
            if self.fallback_font:
                return self.fallback_font.getmask(text, mode, *args, **kwargs)
            raise
    
    def getbbox(self, text, *args, **kwargs):
        """获取文本边界框"""
        return self.primary_font.getbbox(text, *args, **kwargs)
    
    def __getattr__(self, name):
        """代理其他属性到主字体"""
        return getattr(self.primary_font, name)


def load_font_with_cjk_fallback(font_path: str, size: int) -> FontWithFallback:
    """
    加载字体，自动添加CJK回退支持
    
    Args:
        font_path: 主字体文件路径
        size: 字体大小
    
    Returns:
        FontWithFallback: 带回退的字体对象
    """
    # 加载主字体
    try:
        primary_font = ImageFont.truetype(font_path, size)
    except Exception:
        primary_font = ImageFont.load_default()
    
    # 加载CJK字体作为回退（仅使用项目资源中的字体，不查询系统）
    fallback_font = None
    cjk_font_path = _find_cjk_font()
    if cjk_font_path:
        try:
            fallback_font = ImageFont.truetype(cjk_font_path, size)
        except Exception as e:
            # 如果加载失败，记录错误但不抛出异常
            pass
    
    return FontWithFallback(primary_font, fallback_font)


def draw_text_smart(
    draw: ImageDraw.Draw,
    position: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int] = (0, 0, 0)
) -> None:
    """
    智能文本绘制函数，自动处理字体回退
    
    如果传入的font是FontWithFallback类型，会自动使用回退字体处理缺失字符
    否则直接使用普通绘制
    
    Args:
        draw: ImageDraw对象
        position: 文本位置 (x, y)
        text: 要绘制的文本
        font: 字体对象（可以是FontWithFallback或普通字体）
        fill: 文本颜色
    """
    # 如果是FontWithFallback类型，需要特殊处理
    if isinstance(font, FontWithFallback):
        if not font.fallback_font:
            # 没有回退字体，直接绘制
            draw.text(position, text, font=font.primary_font, fill=fill)
            return
        
        # 有回退字体，逐个字符检查并绘制
        x, y = position
        current_x = x
        
        for char in text:
            # 获取适合该字符的字体
            char_font = font._get_font_for_char(char)
            
            # 测量字符宽度
            try:
                bbox = draw.textbbox((0, 0), char, font=char_font)
                char_width = bbox[2] - bbox[0]
            except Exception:
                char_width = font.primary_font.size // 2  # 估算宽度
            
            # 绘制字符
            draw.text((current_x, y), char, font=char_font, fill=fill)
            current_x += char_width
    else:
        # 普通字体，直接绘制
        draw.text(position, text, font=font, fill=fill)
