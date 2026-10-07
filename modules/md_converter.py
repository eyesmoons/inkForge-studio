"""
md_converter.py
Markdown → 微信公众号兼容 HTML

核心功能：
1. 解析 Markdown（mistune v3）
2. 将 CSS 内联到每个 HTML 标签（premailer）
3. 处理代码高亮（可选）
4. 输出微信可直接粘贴/提交的 HTML
"""

import os
import re
import html
import mistune
from premailer import transform
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent
CSS_PATH = BASE_DIR / "templates" / "wechat_style.css"

# ──────────────────────────────────────────
# 排版模板系统
# ──────────────────────────────────────────
# 每套模板包含：颜色方案 + h2/h3 样式 + 引用块样式 + 整体风格
# 向后兼容：旧的 theme 值（blue/green/dark/warm）自动映射到 classic 模板

TEMPLATES = {
    # ── 经典：左边框竖线 + 简洁干净 ──
    "classic": {
        "label": "经典",
        "colors": {
            "accent":     "#4f8ef7",
            "accent_bg":  "#eff4fe",
            "h2_color":   "#1a3a6e",
            "link_color": "#4f8ef7",
        },
        "css": """
/* h2：左边框竖线 */
h2 {{ font-size:20px; font-weight:bold; margin:24px 0 12px; padding:0 0 6px 12px;
     border-left:4px solid {accent}; color:{h2_color}; line-height:1.4; letter-spacing:1px; }}
h3 {{ font-size:18px; font-weight:bold; color:{h2_color}; margin:18px 0 8px; letter-spacing:1px; }}
blockquote {{ border-left:4px solid {accent}; background:{accent_bg}; }}
""",
    },

    # ── 杂志：居中标题 + 底部分割线 ──
    "magazine": {
        "label": "杂志",
        "colors": {
            "accent":     "#333333",
            "accent_bg":  "#f7f7f7",
            "h2_color":   "#1a1a1a",
            "link_color": "#4f8ef7",
        },
        "css": """
/* h2：居中 + 底部分割线 */
h2 {{ font-size:20px; font-weight:bold; margin:28px 0 16px; text-align:center;
     color:{h2_color}; padding-bottom:10px; padding-left:0;
     border-left:none; border-bottom:1px solid {accent}; letter-spacing:2px; }}
h2::after {{ content:''; display:block; width:40px; height:3px;
            background:{accent}; margin:8px auto 0; border-radius:2px; }}
h3 {{ font-size:17px; font-weight:bold; color:{h2_color}; margin:20px 0 10px;
     text-align:center; letter-spacing:1px; border-left:none; }}
blockquote {{ border-left:none; border-top:2px solid {accent}; background:{accent_bg};
             border-radius:4px; padding:14px 18px; }}
""",
    },

    # ── 科技：背景色块 h2 + 引用块带图标感 ──
    "tech": {
        "label": "科技",
        "colors": {
            "accent":     "#00b4d8",
            "accent_bg":  "#f0f9ff",
            "h2_color":   "#023e8a",
            "link_color": "#00b4d8",
        },
        "css": """
/* h2：渐变背景色块 + 圆角 */
h2 {{ font-size:20px; font-weight:bold; margin:24px 0 12px;
     padding:8px 16px; border-radius:6px;
     background:linear-gradient(135deg, {accent_bg} 0%, #fff 100%);
     color:{h2_color}; border-left:4px solid {accent}; letter-spacing:1px; }}
h3 {{ font-size:17px; font-weight:bold; color:{h2_color}; margin:18px 0 8px;
     padding-left:10px; border-left:3px solid {accent}; }}
blockquote {{ border-left:4px solid {accent}; background:{accent_bg};
             border-radius:0 8px 8px 0; padding:14px 18px; }}
""",
    },

    # ── 极简：纯粗体无装饰 + 大量留白 ──
    "minimal": {
        "label": "极简",
        "colors": {
            "accent":     "#666666",
            "accent_bg":  "#fafafa",
            "h2_color":   "#222222",
            "link_color": "#222222",
        },
        "css": """
/* h2：纯粗体无装饰 */
h2 {{ font-size:22px; font-weight:bold; margin:32px 0 16px;
     color:{h2_color}; letter-spacing:1px; border:none; padding:0; }}
h3 {{ font-size:18px; font-weight:bold; color:{h2_color}; margin:24px 0 12px;
     padding:0; border:none; letter-spacing:1px; }}
blockquote {{ border-left:none; background:{accent_bg};
             padding:16px 20px; border-radius:4px;
             font-style:italic; color:#555; }}
""",
    },

    # ── 笔记：带序号装饰 + 便签风格 ──
    "notebook": {
        "label": "笔记",
        "colors": {
            "accent":     "#e17055",
            "accent_bg":  "#fef5f0",
            "h2_color":   "#2d3436",
            "link_color": "#e17055",
        },
        "css": """
/* h2：圆角背景块 + 序号感 */
h2 {{ font-size:19px; font-weight:bold; margin:24px 0 12px;
     padding:8px 14px; border-radius:8px;
     background:{accent_bg}; color:{h2_color}; letter-spacing:1px;
     border:1px solid rgba(225,112,85,0.15); }}
h3 {{ font-size:17px; font-weight:bold; color:{h2_color}; margin:18px 0 8px;
     padding-left:12px; border-left:3px solid {accent}; }}
blockquote {{ border-left:none; background:{accent_bg};
             border-radius:8px; padding:14px 18px;
             border:1px solid rgba(225,112,85,0.1); }}
""",
    },
}

# 旧 theme → 模板映射（向后兼容）
_THEME_TO_TEMPLATE = {
    "blue":  "classic",
    "green": "classic",
    "dark":  "classic",
    "warm":  "classic",
}

# 旧 theme → 颜色覆盖映射
_THEME_COLORS = {
    "green": {"accent": "#07C160", "accent_bg": "#f0faf4", "h2_color": "#1a1a1a", "link_color": "#07C160"},
    "blue":  {"accent": "#4f8ef7", "accent_bg": "#eff4fe", "h2_color": "#1a3a6e", "link_color": "#4f8ef7"},
    "dark":  {"accent": "#a78bfa", "accent_bg": "#1e1a2e", "h2_color": "#e0d9ff", "link_color": "#a78bfa"},
    "warm":  {"accent": "#f5a623", "accent_bg": "#fff8ee", "h2_color": "#5c3a00", "link_color": "#e67e00"},
}


def _build_template_css(template: str = "classic", theme: str = "") -> str:
    """
    根据模板名 + 可选主题色生成覆盖 CSS。

    Args:
        template: 模板名（classic/magazine/tech/minimal/notebook）
        theme:    旧主题名（blue/green/dark/warm），向后兼容

    Returns:
        CSS 字符串
    """
    # 兼容旧调用：如果传的是旧 theme 值，映射到 classic 模板 + 覆盖颜色
    if template in _THEME_COLORS:
        # theme 值被误传为 template 参数
        theme = template
        template = "classic"

    tmpl = TEMPLATES.get(template, TEMPLATES["classic"])
    colors = dict(tmpl["colors"])

    # 如果有旧 theme，覆盖颜色（保持向后兼容的色系偏好）
    if theme and theme in _THEME_COLORS:
        colors.update(_THEME_COLORS[theme])

    # 替换模板中的颜色占位符
    css = tmpl["css"].format(**colors)

    # 补充通用颜色覆盖
    return f"""
/* ── 模板：{tmpl['label']} ── */
{css}
a {{ color: {colors['link_color']}; text-decoration:none; }}
th {{ background: {colors['accent']}; }}
"""


# ──────────────────────────────────────────
# 自定义渲染器：增强微信适配
# ──────────────────────────────────────────
class WeChatRenderer(mistune.HTMLRenderer):
    """针对微信公众号的自定义 HTML 渲染器"""

    def heading(self, children, level, **attrs):
        """标题：h2 加左边框标记"""
        tag = f"h{level}"
        return f"<{tag}>{children}</{tag}>\n"

    def block_code(self, code, **attrs):
        """代码块：深色背景"""
        info = attrs.get("info", "") or ""
        lang = info.split()[0] if info.strip() else "text"
        code_escaped = (
            code.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )
        return (
            f'<pre><code class="language-{lang}">'
            f"{code_escaped}"
            f"</code></pre>\n"
        )

    def codespan(self, code, **attrs):
        """行内代码"""
        return f"<code>{html.escape(code)}</code>"

    def image(self, alt, url, title=None, **attrs):
        """图片：居中显示"""
        title_attr = f' title="{title}"' if title else ""
        return f'<img src="{url}" alt="{alt}"{title_attr} />\n'

    def link(self, text, url, title=None, **attrs):
        """链接：微信内不支持外链跳转，保留文本"""
        return f'<span style="color:#07C160">{text}</span>'

    def thematic_break(self, **attrs):
        return "<hr />\n"

    def block_quote(self, text, **attrs):
        return f"<blockquote>{text}</blockquote>\n"

    # ── 列表转段落 ────────────────────────────────────────
    # 微信公众号文章不适合大量列表，把列表项转为段落文字

    def list_item(self, children, **attrs):
        """列表项 → 段落（去掉圆点/序号）"""
        # children 已经是渲染好的 HTML，提取纯文本段
        text = re.sub(r'<[^>]+>', '', children).strip()
        if text:
            return f"<p>{children.strip()}</p>\n"
        return ""

    def list(self, children, ordered=False, **attrs):
        """无序/有序列表 → 纯段落组合，不加 ul/ol 标签"""
        return children

    # ── 表格转文字描述 ────────────────────────────────────

    def table(self, children, **attrs):
        """表格 → 简洁的描述性段落"""
        # 提取所有单元格文字，拼成可读的段落
        cells = re.findall(r'<t[dh][^>]*>\s*(.*?)\s*</t[dh]>', children, re.DOTALL | re.IGNORECASE)
        clean_cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells if c.strip()]
        if clean_cells:
            text = "　".join(clean_cells)
            return f'<p style="color:#555555;font-size:14px;">{text}</p>\n'
        return ""

    def table_head(self, children, **attrs):
        return children

    def table_body(self, children, **attrs):
        return children

    def table_row(self, children, **attrs):
        return children

    def table_cell(self, children, align=None, is_head=False, **attrs):
        tag = "th" if is_head else "td"
        return f"<{tag}>{children}</{tag}>"


# ──────────────────────────────────────────
# 主转换函数
# ──────────────────────────────────────────
def markdown_to_wechat_html(
    markdown_text: str,
    title: str = "",
    author: str = "",
    add_footer: bool = True,
    theme: str = "blue",
    template: str = "",
    ending_text: str = "",
) -> str:
    """
    将 Markdown 文本转换为微信公众号兼容的 HTML（内联样式）

    Args:
        markdown_text: Markdown 正文
        title:         文章标题（可选，不会渲染到正文）
        author:        作者名（用于尾部署名，仅当 ending_text 为空时使用）
        add_footer:    是否添加文章尾部签名
        theme:         主题色名（green / dark / blue / warm），向后兼容
        template:      排版模板名（classic / magazine / tech / minimal / notebook），优先于 theme
        ending_text:   自定义结尾固定词（优先级高于 author）

    Returns:
        str: 带内联样式的 HTML 字符串
    """

    # 1. 读取样式文件 + 叠加模板/主题色 CSS
    css_content = ""
    if CSS_PATH.exists():
        with open(CSS_PATH, "r", encoding="utf-8") as f:
            css_content = f.read()
    css_content += _build_template_css(template=template, theme=theme)

    # 2. 预处理 Markdown：清理多余空行
    md_text = _preprocess_markdown(markdown_text)

    # 3. 解析 Markdown → HTML
    renderer = WeChatRenderer(escape=False)
    md_parser = mistune.create_markdown(
        renderer=renderer,
        plugins=["strikethrough", "table", "task_lists", "url"],
    )
    raw_html = md_parser(md_text)

    # 4. 添加尾部（避免重复）
    if add_footer and ending_text:
        # 先移除任何已存在的 article-footer（包括 — END — 或 — 作者名 —）
        # 这样可以确保不管用户粘贴什么内容，都只显示自定义结尾词
        import re
        raw_html = re.sub(r'\s*<p\s+class="article-footer"[^>]*>.*?</p>\s*$', '', raw_html, flags=re.DOTALL)

        # 然后检查纯文本末尾是否已经包含结尾词，避免重复
        html_plain = raw_html.replace('<br/>', '\n').replace('<br>', '\n').replace('</p>', '\n')
        html_plain = html_plain.replace('&nbsp;', ' ')
        text_only = re.sub(r'<[^>]+>', '', html_plain).strip()
        if not text_only.endswith(ending_text):
            raw_html += (
                f'\n<p class="article-footer">{ending_text}</p>\n'
            )
    elif add_footer:
        # 没有 ending_text 时，使用作者名或 END
        # 先移除任何已存在的 article-footer
        import re
        raw_html = re.sub(r'\s*<p\s+class="article-footer"[^>]*>.*?</p>\s*$', '', raw_html, flags=re.DOTALL)

        # 再添加新的 footer
        if author:
            footer_text = f"— {author} —"
        else:
            footer_text = "— END —"
        raw_html += (
            f'\n<p class="article-footer">{footer_text}</p>\n'
        )

    # 5. 包裹为完整 HTML（premailer 需要完整结构）
    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
{css_content}
</style>
</head>
<body>
{raw_html}
</body>
</html>"""

    # 6. CSS 内联（premailer）
    inlined_html = transform(
        full_html,
        remove_classes=True,
        strip_important=False,
        allow_network=False,
        allow_loading_external_files=False,
    )

    # 7. 提取 <body> 内容（微信只需要正文部分）
    body_content = _extract_body(inlined_html)

    # 8. 后处理：清理多余属性
    body_content = _postprocess_html(body_content)

    return body_content


def _preprocess_markdown(text: str) -> str:
    """预处理 Markdown 文本"""
    # 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 移除超过2个的连续空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_body(html: str) -> str:
    """从完整 HTML 中提取 <body> 内容"""
    match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return html


def _postprocess_html(html: str) -> str:
    """后处理 HTML：清理微信不兼容的属性"""
    # 移除 data-* 属性
    html = re.sub(r'\s+data-[a-z\-]+=[""][^""]*[""]', "", html)
    # 移除空的 style 属性
    html = re.sub(r'\s+style=""', "", html)
    # 移除 class 属性（premailer 应已处理，双重保险）
    html = re.sub(r'\s+class="[^"]*"', "", html)
    return html


# ──────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────
def save_html(html_content: str, filename: str) -> Path:
    """将 HTML 内容保存到 output/drafts/ 目录"""
    output_dir = BASE_DIR / "output" / "drafts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    with open(output_path, "w", encoding="utf-8") as f:
        # 保存为完整可预览的 HTML
        full = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>预览</title>
<style>
body {{ max-width: 680px; margin: 0 auto; padding: 20px; }}
</style>
</head>
<body>
{html_content}
</body>
</html>"""
        f.write(full)
    return output_path


# ──────────────────────────────────────────
# CLI 测试入口
# ──────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        # 使用内置示例
        sample_md = """
# 用 AI 重新定义内容创作

2026 年，AI 已经不再是未来式——它是现在进行时。

## 为什么说内容创作迎来了拐点

过去，一篇高质量的公众号文章需要：

- 选题调研（1-2小时）
- 撰写初稿（2-4小时）
- 排版美化（0.5-1小时）
- 封面制作（0.5小时）

现在，借助 AI Agent，这些步骤可以压缩到 **5 分钟以内**。

## 核心技术路径

### 第一步：智能选题

```python
# 调用 Kai Skill 生成选题
topic = "AI 内容创作趋势"
article = kai_writer.generate(topic=topic, style="深度")
```

### 第二步：自动排版

> 微信公众号不支持外链 CSS，所有样式必须内联。
> 这正是本工具解决的核心问题。

| 步骤 | 工具 | 耗时 |
|------|------|------|
| MD解析 | mistune | <50ms |
| CSS内联 | premailer | <100ms |
| 封面生成 | image_gen | ~10s |

### 第三步：一键发布

完成排版后，调用微信草稿箱 API，文章自动推送到公众号后台。

## 总结

**效率提升，不是替代创作，而是让创作者专注于真正重要的事：思考和判断。**
"""
        html = markdown_to_wechat_html(sample_md, author="AI 助手")
        out = save_html(html, "sample_preview.html")
        print(f"✅ 转换成功！预览文件：{out}")
        print(f"   HTML 长度：{len(html)} 字符")
    else:
        # 从文件读取
        md_file = sys.argv[1]
        with open(md_file, "r", encoding="utf-8") as f:
            md_content = f.read()
        html = markdown_to_wechat_html(md_content)
        out_name = Path(md_file).stem + "_wechat.html"
        out = save_html(html, out_name)
        print(f"✅ 转换完成：{out}")
