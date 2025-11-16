"""
测试字体回退功能（独立运行版本）
模拟 state.py 中的文字生成逻辑，验证 CJK 字符（特别是繁体中文）是否能正确显示
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

# 设置UTF-8编码（Windows控制台）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from draw.text_utils import load_font_with_cjk_fallback, draw_text_smart, FontWithFallback


def test_load_font_with_cjk_fallback():
    """测试字体加载功能"""
    print("测试1: 字体加载功能...")
    font_path = os.path.join(os.path.dirname(__file__), "..", "draw", "resource", "DouyinSansBold.otf")
    
    # 加载字体
    font = load_font_with_cjk_fallback(font_path, 16)
    
    # 验证返回的是 FontWithFallback 类型
    assert isinstance(font, FontWithFallback), "字体对象类型错误"
    assert font.primary_font is not None, "主字体未加载"
    
    # 验证回退字体是否加载（如果资源目录中有CJK字体）
    if font.fallback_font:
        assert isinstance(font.fallback_font, ImageFont.FreeTypeFont), "回退字体类型错误"
        print("  [OK] 主字体和回退字体都已加载")
    else:
        print("  [WARN] 回退字体未加载（可能资源目录中没有CJK字体）")
    print("  [OK] 测试通过\n")


def test_cjk_char_detection():
    """测试CJK字符检测"""
    print("测试2: CJK字符检测...")
    font_path = os.path.join(os.path.dirname(__file__), "..", "draw", "resource", "DouyinSansBold.otf")
    font = load_font_with_cjk_fallback(font_path, 16)
    
    # 测试各种字符类型
    test_chars = [
        ("計", True),   # 繁体中文
        ("画", True),   # 简体中文
        ("通", True),   # 简体中文
        ("り", True),   # 日文平假名
        ("A", False),   # 英文字母
        ("1", False),   # 数字
        ("!", False),   # 标点符号
    ]
    
    all_passed = True
    for char, expected_is_cjk in test_chars:
        result = font._is_cjk_char(char)
        if result != expected_is_cjk:
            print(f"  [FAIL] 字符 '{char}' 的CJK检测结果不符合预期: 期望 {expected_is_cjk}, 实际 {result}")
            all_passed = False
        else:
            print(f"  [OK] 字符 '{char}': {'CJK' if result else '非CJK'}")
    
    assert all_passed, "CJK字符检测测试失败"
    print("  [OK] 测试通过\n")


def test_font_selection_for_char():
    """测试字符字体选择逻辑"""
    print("测试3: 字符字体选择逻辑...")
    font_path = os.path.join(os.path.dirname(__file__), "..", "draw", "resource", "DouyinSansBold.otf")
    font = load_font_with_cjk_fallback(font_path, 16)
    
    if not font.fallback_font:
        print("  ⚠ 回退字体未加载，跳过此测试\n")
        return
    
    # 测试"計"字（繁体中文，主字体可能不支持）
    char_font = font._get_font_for_char("計")
    assert char_font is not None, "字符'計'没有找到合适的字体"
    print(f"  [OK] 字符'計'选择了字体: {'回退字体' if char_font == font.fallback_font else '主字体'}")
    
    # 测试英文字符（应该使用主字体）
    char_font = font._get_font_for_char("A")
    assert char_font == font.primary_font, "英文字符应该使用主字体"
    print(f"  [OK] 字符'A'选择了主字体")
    print("  [OK] 测试通过\n")


def test_draw_text_smart_with_keikaku():
    """测试绘制"計画通り"文本（完全模拟 state.py 的逻辑）"""
    print("测试4: 绘制'計画通り'文本...")
    font_path = os.path.join(os.path.dirname(__file__), "..", "draw", "resource", "DouyinSansBold.otf")
    
    # 模拟 state.py 中的字体加载
    small_font = load_font_with_cjk_fallback(font_path, 16)
    
    # 创建测试图像（模拟 state.py 中的画布）
    width, height = 620, 540
    image = Image.new('RGB', (width, height), (245, 251, 255))
    draw = ImageDraw.Draw(image)
    
    # 测试文本（包含繁体中文"計"）
    title_text = "計画通り"
    rare_color = (149, 117, 205)  # COLOR_RARE
    
    # 使用 draw_text_smart 绘制（完全模拟 state.py 中的调用）
    position = (100, 50)
    draw_text_smart(
        draw,
        position,
        title_text,
        small_font,
        rare_color
    )
    
    # 保存图片
    output_path = os.path.join(os.path.dirname(__file__), "test_keikaku_output.png")
    image.save(output_path)
    print(f"  图片已保存到: {output_path}")
    
    # 验证图像已生成（不会抛出异常）
    assert image is not None, "图像生成失败"
    
    # 验证文本宽度（如果绘制成功，应该有宽度）
    if isinstance(small_font, FontWithFallback):
        # 检查每个字符是否都能正确选择字体
        for char in title_text:
            char_font = small_font._get_font_for_char(char)
            assert char_font is not None, f"字符 '{char}' 没有找到合适的字体"
            
            # 验证字体能生成有效的mask
            try:
                mask = char_font.getmask(char)
                assert mask.size[0] > 0 and mask.size[1] > 0, f"字符 '{char}' 的字体无法生成有效mask"
                print(f"  [OK] 字符 '{char}' 可以正确渲染")
            except Exception as e:
                print(f"  [FAIL] 字符 '{char}' 渲染失败: {e}")
                raise
    
    print("  [OK] 测试通过\n")


def test_draw_text_smart_with_mixed_chars():
    """测试混合字符文本绘制"""
    print("测试5: 混合字符文本绘制...")
    font_path = os.path.join(os.path.dirname(__file__), "..", "draw", "resource", "DouyinSansBold.otf")
    small_font = load_font_with_cjk_fallback(font_path, 16)
    
    image = Image.new('RGB', (400, 100), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    
    # 测试混合文本
    test_texts = [
        "計画通り",      # 繁体中文+日文
        "满图鉴了！",    # 简体中文+标点
        "ABC123",        # 英文+数字
        "测试Test123",   # 混合
    ]
    
    for text in test_texts:
        try:
            draw_text_smart(draw, (10, 10), text, small_font, (0, 0, 0))
            print(f"  [OK] 文本 '{text}' 绘制成功")
        except Exception as e:
            print(f"  [FAIL] 绘制文本 '{text}' 失败: {e}")
            raise
    
    print("  [OK] 测试通过\n")


def test_font_fallback_for_specific_char():
    """专门测试"計"字的字体选择"""
    print("测试6: '計'字的字体选择...")
    font_path = os.path.join(os.path.dirname(__file__), "..", "draw", "resource", "DouyinSansBold.otf")
    font = load_font_with_cjk_fallback(font_path, 16)
    
    if not font.fallback_font:
        print("  ⚠ 回退字体未加载，跳过此测试\n")
        return
    
    # 测试"計"字
    char = "計"
    
    # 获取主字体和回退字体的mask
    primary_mask = font.primary_font.getmask(char)
    fallback_mask = font.fallback_font.getmask(char)
    
    print(f"  主字体mask大小: {primary_mask.size}")
    print(f"  回退字体mask大小: {fallback_mask.size}")
    
    # 选择字体
    selected_font = font._get_font_for_char(char)
    
    # 验证：如果主字体的mask为空或与回退字体不同，应该使用回退字体
    if (primary_mask.size[0] == 0 or 
        primary_mask.size != fallback_mask.size or 
        primary_mask.tobytes() != fallback_mask.tobytes()):
        assert selected_font == font.fallback_font, "主字体不支持'計'字，应该使用回退字体"
        print("  [OK] 主字体不支持'計'字，已使用回退字体")
    else:
        print("  [OK] 主字体支持'計'字")
    
    # 验证选中的字体能正确渲染
    selected_mask = selected_font.getmask(char)
    assert selected_mask.size[0] > 0 and selected_mask.size[1] > 0, "选中的字体无法正确渲染'計'字"
    print(f"  [OK] 选中的字体可以正确渲染'計'字 (mask大小: {selected_mask.size})")
    print("  [OK] 测试通过\n")


def test_state_panel_title_rendering():
    """完全模拟 state.py 中称号绘制的逻辑"""
    print("测试7: 模拟state.py中称号绘制逻辑...")
    font_path = os.path.join(os.path.dirname(__file__), "..", "draw", "resource", "DouyinSansBold.otf")
    
    # 模拟 state.py 中的设置
    small_font = load_font_with_cjk_fallback(font_path, 16)
    rare_color = (149, 117, 205)  # COLOR_RARE
    
    # 创建画布（模拟 state.py）- 使用渐变背景
    from draw.gradient_utils import create_vertical_gradient
    width, height = 620, 540
    bg_top = (174, 214, 241)  # 柔和天蓝色
    bg_bot = (245, 251, 255)  # 温和淡蓝色
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 模拟用户数据
    current_title = {
        'name': '計画通り'
    }
    
    # 模拟 state.py 中的绘制逻辑
    col1_x = 100
    row1_y = 50
    nickname_width = 80  # 模拟昵称宽度
    
    # 绘制昵称（模拟）
    nickname = "Lecon"
    subtitle_font = ImageFont.truetype(font_path, 24)
    primary_medium = (74, 105, 134)  # 柔和中蓝
    draw.text((col1_x, row1_y), nickname, font=subtitle_font, fill=primary_medium)
    
    if current_title:
        if isinstance(current_title, dict):
            title_text = f"{current_title.get('name', '未知称号')}"
        else:
            title_text = f"{current_title}"
        
        print(f"  绘制称号文本: '{title_text}'")
        
        # 使用智能文本绘制（完全模拟 state.py）
        draw_text_smart(
            draw,
            (col1_x + nickname_width + 10, row1_y + 5),
            title_text,
            small_font,
            rare_color
        )
        
        # 保存图片
        output_path = os.path.join(os.path.dirname(__file__), "test_state_panel_output.png")
        image.save(output_path)
        print(f"  图片已保存到: {output_path}")
        
        # 验证绘制成功
        assert image is not None, "图像生成失败"
        
        # 验证每个字符都能找到合适的字体
        for char in title_text:
            if isinstance(small_font, FontWithFallback):
                char_font = small_font._get_font_for_char(char)
                assert char_font is not None, f"字符 '{char}' 没有找到合适的字体"
                
                # 验证字体能生成有效渲染
                try:
                    mask = char_font.getmask(char)
                    assert mask.size[0] > 0 and mask.size[1] > 0, f"字符 '{char}' 无法正确渲染"
                    print(f"  [OK] 字符 '{char}' 可以正确渲染")
                except Exception:
                    print(f"  [FAIL] 字符 '{char}' 渲染失败")
                    raise
    
    print("  [OK] 测试通过\n")


def test_man_tu_jian_title():
    """测试'满图鉴了'称号"""
    print("测试8: 测试'满图鉴了'称号...")
    font_path = os.path.join(os.path.dirname(__file__), "..", "draw", "resource", "DouyinSansBold.otf")
    
    # 模拟 state.py 中的设置
    small_font = load_font_with_cjk_fallback(font_path, 16)
    rare_color = (149, 117, 205)  # COLOR_RARE
    
    # 创建画布（模拟 state.py）- 使用渐变背景
    from draw.gradient_utils import create_vertical_gradient
    width, height = 620, 540
    bg_top = (174, 214, 241)  # 柔和天蓝色
    bg_bot = (245, 251, 255)  # 温和淡蓝色
    image = create_vertical_gradient(width, height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)
    
    # 模拟用户数据
    current_title = {
        'name': '满图鉴了'
    }
    
    # 模拟 state.py 中的绘制逻辑
    col1_x = 100
    row1_y = 50
    nickname_width = 80  # 模拟昵称宽度
    
    # 绘制昵称（模拟）
    nickname = "Lecon"
    subtitle_font = ImageFont.truetype(font_path, 24)
    primary_medium = (74, 105, 134)  # 柔和中蓝
    draw.text((col1_x, row1_y), nickname, font=subtitle_font, fill=primary_medium)
    
    if current_title:
        if isinstance(current_title, dict):
            title_text = f"{current_title.get('name', '未知称号')}"
        else:
            title_text = f"{current_title}"
        
        print(f"  绘制称号文本: '{title_text}'")
        
        # 使用智能文本绘制（完全模拟 state.py）
        draw_text_smart(
            draw,
            (col1_x + nickname_width + 10, row1_y + 5),
            title_text,
            small_font,
            rare_color
        )
        
        # 保存图片
        output_path = os.path.join(os.path.dirname(__file__), "test_man_tu_jian_output.png")
        image.save(output_path)
        print(f"  图片已保存到: {output_path}")
        
        # 验证绘制成功
        assert image is not None, "图像生成失败"
        
        # 验证每个字符都能找到合适的字体
        for char in title_text:
            if isinstance(small_font, FontWithFallback):
                char_font = small_font._get_font_for_char(char)
                assert char_font is not None, f"字符 '{char}' 没有找到合适的字体"
                
                # 验证字体能生成有效渲染
                try:
                    mask = char_font.getmask(char)
                    assert mask.size[0] > 0 and mask.size[1] > 0, f"字符 '{char}' 无法正确渲染"
                    print(f"  [OK] 字符 '{char}' 可以正确渲染")
                except Exception:
                    print(f"  [FAIL] 字符 '{char}' 渲染失败")
                    raise
    
    print("  [OK] 测试通过\n")


if __name__ == "__main__":
    print("=" * 60)
    print("字体回退功能测试")
    print("=" * 60 + "\n")
    
    tests = [
        test_load_font_with_cjk_fallback,
        test_cjk_char_detection,
        test_font_selection_for_char,
        test_draw_text_smart_with_keikaku,
        test_draw_text_smart_with_mixed_chars,
        test_font_fallback_for_specific_char,
        test_state_panel_title_rendering,
        test_man_tu_jian_title,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] 断言失败: {e}\n")
            failed += 1
        except Exception as e:
            print(f"  [FAIL] 测试失败: {e}\n")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)

