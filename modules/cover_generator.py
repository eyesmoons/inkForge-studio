"""
cover_generator.py
自动生成微信公众号封面图

功能：
1. 根据文章标题/关键词生成 AI 封面图（调用 WorkBuddy image_gen）
2. 本地备用方案：用 Pillow 生成纯色+文字封面（无需网络）
3. 自动裁切/缩放为微信标准封面尺寸 900×383px
4. 保存至 output/covers/

微信公众号封面图规范：
- 尺寸：900 × 383 px（约 2.35:1）
- 格式：JPG / PNG
- 大小：< 5MB
"""

import os
import re
import sys
import json
import hashlib
import textwrap
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# 项目根目录
BASE_DIR = Path(__file__).parent.parent
COVERS_DIR = BASE_DIR / "output" / "covers"

# 微信封面标准尺寸
COVER_WIDTH = 900
COVER_HEIGHT = 383

# 微信绿配色方案
THEMES = {
    "green": {
        "bg": [(7, 193, 96), (5, 150, 70)],        # 绿色渐变
        "accent": (255, 255, 255),
        "title_color": (255, 255, 255),
        "sub_color": (220, 255, 230),
        "dot_color": (255, 255, 255, 60),
    },
    "dark": {
        "bg": [(30, 30, 46), (17, 17, 27)],         # 深色渐变
        "accent": (7, 193, 96),
        "title_color": (255, 255, 255),
        "sub_color": (160, 160, 180),
        "dot_color": (7, 193, 96, 40),
    },
    "blue": {
        "bg": [(24, 144, 255), (10, 90, 200)],      # 蓝色渐变
        "accent": (255, 255, 255),
        "title_color": (255, 255, 255),
        "sub_color": (200, 225, 255),
        "dot_color": (255, 255, 255, 50),
    },
    "warm": {
        "bg": [(255, 89, 64), (220, 50, 30)],       # 暖色渐变
        "accent": (255, 220, 0),
        "title_color": (255, 255, 255),
        "sub_color": (255, 220, 210),
        "dot_color": (255, 255, 255, 40),
    },
}


def generate_cover(
    title: str,
    keywords: list[str] = None,
    author: str = "",
    theme: str = "blue",
    output_filename: str = None,
    ai_prompt: str = None,
) -> Path:
    """
    生成公众号封面图

    Args:
        title:           文章标题（显示在封面上）
        keywords:        关键词列表（显示为标签）
        author:          作者名
        theme:           配色主题 green / dark / blue / warm
        output_filename: 输出文件名（不含扩展名）
        ai_prompt:       AI 绘图提示词（若提供则优先尝试 AI 生成）

    Returns:
        Path: 生成的封面图路径
    """
    COVERS_DIR.mkdir(parents=True, exist_ok=True)

    if output_filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^\w\u4e00-\u9fff]", "_", title[:20])
        output_filename = f"cover_{ts}_{slug}"

    output_path = COVERS_DIR / f"{output_filename}.jpg"

    # 优先：如果有 AI prompt，尝试调用 image_gen（WorkBuddy 环境）
    if ai_prompt:
        ai_result = _try_ai_cover(ai_prompt, output_path)
        if ai_result:
            # AI 生成成功，裁切为标准尺寸
            final_path = _resize_to_wechat_cover(ai_result, output_path)
            print(f"✅ AI 封面生成成功：{final_path}")
            return final_path

    # 备用：Pillow 本地生成
    if PIL_AVAILABLE:
        path = _generate_local_cover(
            title=title,
            keywords=keywords or [],
            author=author,
            theme=theme,
            output_path=output_path,
        )
        print(f"✅ 本地封面生成成功：{path}")
        return path
    else:
        raise RuntimeError("Pillow 未安装，请运行：pip install Pillow")


def _try_ai_cover(prompt: str, output_path: Path) -> Optional[Path]:
    """
    尝试通过 WorkBuddy image_gen 生成封面
    （此函数在 WorkBuddy Agent 环境内调用时生效）
    """
    # 在 WorkBuddy Agent 执行环境中，image_gen 是通过 Agent 工具调用的
    # 在直接 Python 调用时，此处返回 None，退回本地生成
    # Agent 会在 main.py 中直接调用 image_gen 工具，然后传递图片路径给本模块
    return None


def _generate_local_cover(
    title: str,
    keywords: list,
    author: str,
    theme: str,
    output_path: Path,
) -> Path:
    """用 Pillow 生成高质量纯色渐变封面"""

    t = THEMES.get(theme, THEMES["green"])
    img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), t["bg"][0])
    draw = ImageDraw.Draw(img, "RGBA")

    # ── 背景渐变 ──────────────────────────────
    _draw_gradient(img, t["bg"][0], t["bg"][1])

    # ── 装饰圆点（右侧） ───────────────────────
    _draw_decorative_circles(draw, t["dot_color"])

    # ── 左侧强调色竖条 ─────────────────────────
    bar_color = t["accent"] if theme != "green" else (255, 255, 255, 180)
    draw.rectangle([(50, 60), (57, COVER_HEIGHT - 60)], fill=bar_color)

    # ── 字体加载（优先系统中文字体）─────────────
    title_font = _get_font(size=42, bold=True)
    sub_font   = _get_font(size=22, bold=False)
    tag_font   = _get_font(size=18, bold=False)
    author_font = _get_font(size=18, bold=False)

    # ── 标题（自动换行）─────────────────────────
    title_lines = _wrap_text(title, max_width=680, font=title_font, draw=draw)
    y_title = _calc_title_y(len(title_lines))

    for i, line in enumerate(title_lines):
        draw.text(
            (80, y_title + i * 54),
            line,
            font=title_font,
            fill=t["title_color"],
        )

    # ── 关键词标签 ────────────────────────────
    if keywords:
        tag_y = y_title + len(title_lines) * 54 + 20
        _draw_keyword_tags(draw, keywords[:4], tag_y, t, tag_font)

    # ── 底部装饰线 ────────────────────────────
    line_color = (*t["accent"][:3], 120) if len(t["accent"]) == 3 else t["accent"]
    draw.rectangle(
        [(80, COVER_HEIGHT - 20), (COVER_WIDTH - 80, COVER_HEIGHT - 17)],
        fill=line_color,
    )

    # ── 轻微模糊背景圆（增加层次感）──────────────
    _add_blur_circle(img, theme)

    img.save(str(output_path), "JPEG", quality=92, optimize=True)
    return output_path


def _draw_gradient(img: Image.Image, color1: tuple, color2: tuple):
    """绘制从左到右的渐变背景"""
    draw = ImageDraw.Draw(img)
    for x in range(COVER_WIDTH):
        ratio = x / COVER_WIDTH
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        draw.line([(x, 0), (x, COVER_HEIGHT)], fill=(r, g, b))


def _draw_decorative_circles(draw: ImageDraw.Draw, color: tuple):
    """在右侧绘制装饰性半透明圆圈"""
    circles = [
        (COVER_WIDTH - 60,  -40, 180),
        (COVER_WIDTH + 20, 200, 240),
        (COVER_WIDTH - 200, COVER_HEIGHT + 30, 140),
    ]
    for cx, cy, r in circles:
        draw.ellipse(
            [(cx - r, cy - r), (cx + r, cy + r)],
            fill=color,
        )


def _add_blur_circle(img: Image.Image, theme: str):
    """在图像右上角叠加一个模糊光晕效果"""
    overlay = Image.new("RGBA", (COVER_WIDTH, COVER_HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    glow_color = {
        "green": (100, 255, 150, 30),
        "dark":  (7, 193, 96, 20),
        "blue":  (100, 180, 255, 25),
        "warm":  (255, 180, 100, 25),
    }.get(theme, (255, 255, 255, 20))

    od.ellipse(
        [(COVER_WIDTH - 200, -100), (COVER_WIDTH + 100, 300)],
        fill=glow_color,
    )
    blurred = overlay.filter(ImageFilter.GaussianBlur(radius=40))
    img.paste(Image.fromarray(
        __import__("numpy", fromlist=["array"]).array(img)
    ), (0, 0)) if False else None  # noqa（不做 numpy 依赖）

    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, blurred)
    img.paste(img_rgba.convert("RGB"))


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """获取字体（自动查找系统中文字体）"""
    font_candidates = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        # Linux
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # 退回到默认字体
    return ImageFont.load_default()


def _wrap_text(text: str, max_width: int, font, draw: ImageDraw.Draw) -> list:
    """将文本按宽度自动换行"""
    lines = []
    # 先按换行符分割
    for para in text.split("\n"):
        current_line = ""
        for char in para:
            test_line = current_line + char
            w = draw.textlength(test_line, font=font)
            if w <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
    return lines[:3]  # 最多3行


def _calc_title_y(num_lines: int) -> int:
    """计算标题起始 Y 坐标（垂直居中）"""
    total_height = num_lines * 54
    return max(60, (COVER_HEIGHT - total_height) // 2 - 20)


def _draw_keyword_tags(draw, keywords, y, theme, font):
    """绘制关键词标签"""
    x = 80
    for kw in keywords:
        text = f"# {kw}"
        w = draw.textlength(text, font=font) + 20
        # 标签背景
        draw.rounded_rectangle(
            [(x, y), (x + w, y + 30)],
            radius=4,
            fill=(*theme["accent"][:3], 50),
        )
        draw.text((x + 10, y + 5), text, font=font, fill=theme["sub_color"])
        x += w + 12
        if x > COVER_WIDTH - 100:
            break


def _resize_to_wechat_cover(src_path: Path, dst_path: Path) -> Path:
    """将任意图片裁切/缩放为微信封面标准尺寸 900×383"""
    img = Image.open(str(src_path))
    # 等比例缩放，裁切居中
    target_ratio = COVER_WIDTH / COVER_HEIGHT
    src_ratio = img.width / img.height

    if src_ratio > target_ratio:
        # 图片更宽：以高度为基准缩放，裁剪两侧
        new_h = COVER_HEIGHT
        new_w = int(img.width * new_h / img.height)
    else:
        # 图片更高：以宽度为基准缩放，裁剪上下
        new_w = COVER_WIDTH
        new_h = int(img.height * new_w / img.width)

    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - COVER_WIDTH) // 2
    top = (new_h - COVER_HEIGHT) // 2
    img = img.crop((left, top, left + COVER_WIDTH, top + COVER_HEIGHT))
    img.save(str(dst_path), "JPEG", quality=92)
    return dst_path


def build_cover_prompt(title: str, keywords: list = None, style: str = "tech", theme: str = "green") -> str:
    """
    根据文章信息构建 AI 封面图 Prompt

    Args:
        title:    文章标题
        keywords: 关键词列表
        style:    风格 tech / nature / business / minimal
        theme:    主题颜色 green / dark / blue / warm

    Returns:
        str: 英文 Prompt（适配 image_gen）
    """
    style_desc = {
        "tech":     "futuristic technology, circuit patterns, glowing light effects, digital elements",
        "nature":   "natural scenery, soft light, peaceful atmosphere, organic shapes",
        "business": "professional business, clean office environment, modern design, abstract concepts",
        "minimal":  "minimalist flat illustration, geometric shapes, clean lines, simple composition",
    }.get(style, "modern clean design")

    # 根据主题色配置提示词
    theme_colors = {
        "green": "green (#07C160) and white",
        "dark":  "dark purple (#a78bfa) and deep blue",
        "blue":  "blue (#4f8ef7) and white",
        "warm":  "orange (#f5a623) and cream",
    }.get(theme, "green (#07C160) and white")

    # 使用标题和关键词构建主题描述
    topic_desc = ""
    if keywords:
        topic_desc = f"Related to: {', '.join(keywords[:3])}"
    if title:
        if topic_desc:
            topic_desc += f". Theme: {title}"
        else:
            topic_desc = f"Theme: {title}"

    prompt = (
        f"Professional WeChat official account article cover image. "
        f"{topic_desc}. "
        f"Style: {style_desc}, "
        f"dominant colors {theme_colors}, "
        f"no text overlay, no watermark, no logos, "
        f"high quality, sharp focus, 900x383 aspect ratio landscape format, "
        f"unique composition that reflects the article topic."
    )
    return prompt


# ──────────────────────────────────────────
# CLI 测试入口
# ──────────────────────────────────────────
if __name__ == "__main__":
    import sys

    print("🎨 封面图生成器测试")

    test_cases = [
        {
            "title": "用 AI 重新定义内容创作",
            "keywords": ["人工智能", "公众号运营", "自动化"],
            "author": "AI 助手",
            "theme": "green",
            "filename": "test_cover_green",
        },
        {
            "title": "2026年最值得关注的\n技术趋势",
            "keywords": ["科技", "趋势", "前沿"],
            "author": "Tech Weekly",
            "theme": "dark",
            "filename": "test_cover_dark",
        },
        {
            "title": "深度解析：大模型时代的\n产品设计方法论",
            "keywords": ["产品设计", "AI", "方法论"],
            "author": "产品人",
            "theme": "blue",
            "filename": "test_cover_blue",
        },
    ]

    for tc in test_cases:
        path = generate_cover(
            title=tc["title"],
            keywords=tc["keywords"],
            author=tc["author"],
            theme=tc["theme"],
            output_filename=tc["filename"],
        )
        print(f"   → 主题 [{tc['theme']}] ：{path}")

    print("\n✅ 所有封面生成完毕！")
    print(f"   封面目录：{COVERS_DIR}")

    # 打印封面 Prompt 示例
    prompt = build_cover_prompt(
        title="用 AI 重新定义内容创作",
        keywords=["人工智能", "内容创作", "自动化"],
        style="tech",
        theme="green"
    )
    print(f"\n📝 AI 封面 Prompt 示例：\n{prompt}")
