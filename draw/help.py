import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def draw_help_image():
    # 画布宽度（高度将自适应计算）
    width = 800

    # 1. 创建渐变背景
    def create_vertical_gradient(w, h, top_color, bottom_color):
        base = Image.new('RGB', (w, h), top_color)
        top_r, top_g, top_b = top_color
        bot_r, bot_g, bot_b = bottom_color
        draw = ImageDraw.Draw(base)
        for y in range(h):
            ratio = y / (h - 1)
            r = int(top_r + (bot_r - top_r) * ratio)
            g = int(top_g + (bot_g - top_g) * ratio)
            b = int(top_b + (bot_b - top_b) * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        return base

    bg_top = (240, 248, 255)  # 浅蓝
    bg_bot = (255, 255, 255)  # 白

    # 2. 加载字体
    def load_font(name, size):
        path = os.path.join(os.path.dirname(__file__), "resource", name)
        try:
            return ImageFont.truetype(path, size)
        except:
            return ImageFont.load_default()

    title_font = load_font("DouyinSansBold.otf", 32)
    subtitle_font = load_font("DouyinSansBold.otf", 28)
    section_font = load_font("DouyinSansBold.otf", 24)
    cmd_font = load_font("DouyinSansBold.otf", 18)
    desc_font = load_font("DouyinSansBold.otf", 16)

    # 3. 颜色定义
    title_color = (30, 80, 162)
    cmd_color = (40, 40, 40)
    card_bg = (255, 255, 255)
    line_color = (200, 200, 200)
    shadow_color = (0, 0, 0, 80)

    # 4. 获取文本尺寸的辅助函数（测量版）
    _measure_img = Image.new('RGB', (10, 10), bg_bot)
    _measure_draw = ImageDraw.Draw(_measure_img)
    def measure_text_size(text, font):
        bbox = _measure_draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    # 5. 处理logo背景色的函数
    def replace_white_background(img, new_bg_color=bg_top, threshold=240):
        """将图片的白色背景替换为指定颜色"""
        img = img.convert("RGBA")
        data = img.getdata()
        new_data = []

        for item in data:
            r, g, b = item[:3]
            alpha = item[3] if len(item) > 3 else 255

            # 如果像素接近白色，就替换为新背景色
            if r >= threshold and g >= threshold and b >= threshold:
                new_data.append((*new_bg_color, alpha))
            else:
                new_data.append(item)

        img.putdata(new_data)
        return img

    # 6. Logo/标题布局（先定义数值，稍后绘制）
    logo_size = 160
    logo_x = 30
    logo_y = 25
    title_y = logo_y + logo_size // 2

    # 7. 圆角矩形＋阴影 helper
    def draw_card(x0, y0, x1, y1, radius=12):
        # 简化阴影效果
        shadow_offset = 3
        # 绘制阴影
        draw.rounded_rectangle([x0 + shadow_offset, y0 + shadow_offset, x1 + shadow_offset, y1 + shadow_offset],
                               radius, fill=(220, 220, 220))
        # 白色卡片
        draw.rounded_rectangle([x0, y0, x1, y1], radius, fill=card_bg, outline=line_color, width=1)

    # 8. 绘制章节和命令
    def draw_section(title, cmds, y_start, cols=3):
        # 章节标题左对齐
        title_x = 50
        draw.text((title_x, y_start), title, fill=title_color, font=section_font, anchor="lm")
        w, h = get_text_size(title, section_font)

        # 标题下划线
        underline_y = y_start + h // 2 + 8
        draw.line([(title_x, underline_y), (title_x + w, underline_y)],
                  fill=title_color, width=3)

        y = y_start + h // 2 + 25

        card_w = (width - 60) // cols
        card_h = 85
        pad = 15

        for idx, (cmd, desc) in enumerate(cmds):
            col = idx % cols
            row = idx // cols
            x0 = 30 + col * card_w
            y0 = y + row * (card_h + pad)
            x1 = x0 + card_w - 10
            y1 = y0 + card_h

            draw_card(x0, y0, x1, y1)

            # 文本居中显示
            cx = (x0 + x1) // 2
            # 命令文本
            draw.text((cx, y0 + 18), cmd, fill=cmd_color, font=cmd_font, anchor="mt")
            # 描述文本 - 支持多行
            desc_lines = desc.split('\n') if '\n' in desc else [desc]
            for i, line in enumerate(desc_lines):
                draw.text((cx, y0 + 45 + i * 18), line, fill=(100, 100, 100), font=desc_font, anchor="mt")

        rows = math.ceil(len(cmds) / cols)
        return y + rows * (card_h + pad) + 35

    # 9. 各段命令数据
    basic = [
        ("注册", "注册用户"),
        ("钓鱼", "进行一次钓鱼"),
        ("签到", "每日签到"),
        ("自动钓鱼", "开启/关闭\n自动钓鱼"),
        ("钓鱼区域", "查看钓鱼\n的区域"),
        ("钓鱼记录", "查看钓鱼记录")
    ]

    inventory = [
        ("鱼塘", "查看用户\n鱼塘内的鱼"),
        ("鱼塘容量", "查看鱼塘容量"),
        ("升级鱼塘", "升级鱼塘容量"),
        ("背包", "查看用户\n所有装备"),
        ("鱼竿", "查看用户\n鱼竿信息"),
        ("鱼饵", "查看用户\n鱼饵信息"),
        ("饰品", "查看用户\n饰品信息"),
        ("使用鱼竿 [ID]", "使用鱼竿"),
        ("精炼鱼竿 [ID]", "精炼鱼竿"),
        ("使用鱼饵 [ID]", "使用鱼饵"),
        ("使用饰品 [ID]", "使用饰品"),
        ("精炼饰品 [ID]", "精炼饰品"),
        ("金币", "查看用户\n金币信息"),
        ("高级货币", "查看用户\n高级货币")
    ]

    market = [
        ("全部卖出", "卖出用户\n所有鱼"),
        ("保留卖出", "卖出用户鱼\n保留每种一条"),
        ("出售稀有度 [1-5]", "按稀有度\n出售鱼"),
        ("出售鱼竿 [ID]", "出售鱼竿"),
        ("出售所有鱼竿", "出售所有\n非五星的鱼竿"),
        ("出售饰品 [ID]", "出售饰品"),
        ("出售所有饰品", "出售所有\n非五星的饰品"),
        ("商店", "查看商店信息"),
        ("购买鱼竿 [ID]", "购买鱼竿"),
        ("购买鱼饵 [ID]", "购买鱼饵"),
        ("市场", "查看市场"),
        ("上架鱼竿 [ID]", "上架鱼竿\n到市场"),
        ("上架饰品 [ID]", "上架饰品\n到市场"),
        ("购买 [ID]", "购买市场上\n的物品"),
        ("我的上架", "查看我的\n上架商品"),
        ("下架 [ID]", "下架指定\n商品")
    ]

    gacha = [
        ("抽卡 <1-2>", "抽卡游戏"),
        ("十连 [1-2]", "对1或2卡池\n进行十连抽卡"),
        ("查看卡池 [1-2]", "查看卡池"),
        ("抽卡记录", "查看抽卡记录"),
        ("擦弹 [金币数]", "用金币数\n进行擦弹"),
        ("擦弹 [特殊参数]", "同上，但参数可以为：\n梭哈/梭一半/allin/halfin"),
        ("擦弹记录", "查看擦弹记录")
    ]

    social = [
        ("排行榜", "查看排行榜"),
        ("偷鱼 @群友", "偷群友鱼塘里的一条鱼"),
        ("查看称号", "查看我的称号"),
        ("使用称号 [ID]", "使用称号"),
        ("查看成就", "查看成就"),
        ("税收记录", "查看税收记录"),
        ("鱼类图鉴", "查看鱼类图鉴")
    ]

    admin = [
        ("修改金币 [用户ID] [金币数]", "将用户的金币修改为金币数"),
        ("奖励金币 [用户ID] [金币数]", "奖励用户金币"),
        ("扣除金币 [用户ID] [金币数]", "扣除用户金币"),
        ("修改高级货币 [用户ID] [数量]", "将用户的高级货币修改为数量"),
        ("奖励高级货币 [用户ID] [数量]", "奖励用户高级货币"),
        ("扣除高级货币 [用户ID] [数量]", "扣除用户高级货币"),
        ("全体奖励金币 [数量]", "给全体用户\n发放金币"),
        ("全体奖励高级货币 [数量]", "给全体用户\n发放高级货币"),
        ("全体扣除金币 [数量]", "从全体用户\n扣除金币"),
        ("全体扣除高级货币 [数量]", "从全体用户\n扣除高级货币"),
        ("开启钓鱼后台管理", "开启钓鱼后台管理"),
        ("关闭钓鱼后台管理", "关闭钓鱼后台管理")
    ]

    # 10. 先计算自适应高度
    def section_delta(item_count: int, cols: int) -> int:
        rows = math.ceil(item_count / cols) if item_count > 0 else 0
        # 与 draw_section 中的垂直占位保持一致：h//2+25 起始 + rows*(card_h+pad) + 35
        _, h = measure_text_size("标题", section_font)
        card_h = 85
        pad = 15
        return (h // 2 + 25) + rows * (card_h + pad) + 35

    y0_est = logo_y + logo_size + 30
    y0_est += section_delta(len(basic), 3)
    y0_est += section_delta(len(inventory), 3)
    y0_est += section_delta(len(market), 3)
    y0_est += section_delta(len(gacha), 3)
    y0_est += section_delta(len(social), 2)
    y0_est += section_delta(len(admin), 2)
    footer_y_est = y0_est + 20
    final_height = footer_y_est + 30

    # 用最终高度创建画布，然后进行真正绘制
    image = create_vertical_gradient(width, final_height, bg_top, bg_bot)
    draw = ImageDraw.Draw(image)

    # 绘制 Logo 和 标题
    try:
        logo = Image.open(os.path.join(os.path.dirname(__file__), "resource", "astrbot_logo.jpg"))
        logo = replace_white_background(logo, bg_top)
        logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
        mask = Image.new("L", logo.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, logo.size[0], logo.size[1]], 20, fill=255)
        output = Image.new("RGBA", logo.size, (0, 0, 0, 0))
        output.paste(logo, (0, 0))
        output.putalpha(mask)
        image.paste(output, (logo_x, logo_y), output)
    except Exception as e:
        # 如果没有logo文件，绘制一个圆角占位符
        draw.rounded_rectangle((logo_x, logo_y, logo_x + logo_size, logo_y + logo_size),
                               20, fill=bg_top, outline=(180, 180, 180), width=2)
        draw.text((logo_x + logo_size // 2, logo_y + logo_size // 2), "LOGO",
                  fill=(120, 120, 120), font=subtitle_font, anchor="mm")

    draw.text((width // 2, title_y), "钓鱼游戏帮助", fill=title_color, font=title_font, anchor="mm")

    # 重新基于真实 draw 定义尺寸函数
    def get_text_size(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    # 10+. 按顺序绘制各个部分
    y0 = logo_y + logo_size + 30
    y0 = draw_section("🎣 基础与核心玩法", basic, y0, cols=3)
    y0 = draw_section("🎒 背包与资产管理", inventory, y0, cols=3)
    y0 = draw_section("🛒 商店与市场", market, y0, cols=3)
    y0 = draw_section("🎰 抽卡与概率玩法", gacha, y0, cols=3)
    y0 = draw_section("👥 社交功能", social, y0, cols=2)
    y0 = draw_section("⚙️ 管理后台（管理员）", admin, y0, cols=2)

    # 添加底部信息
    footer_y = y0 + 20
    draw.text((width // 2, footer_y), "💡 提示：命令中的 [ID] 表示必填参数，<> 表示可选参数",
              fill=(120, 120, 120), font=desc_font, anchor="mm")

    # 11. 保存（高度已自适应，无需再次裁剪）
    final_height = footer_y + 30
    image = image.crop((0, 0, width, final_height))

    output_path = "fishing_commands_beautiful.png"
    image.save(output_path, quality=95)
    return output_path
