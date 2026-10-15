"""生成墨锻工坊 PPT 演讲稿"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# ── 颜色方案 ──
INK_DARK = RGBColor(0x1a, 0x1a, 0x2e)
INK_ACCENT = RGBColor(0x07, 0xc1, 0x60)
INK_BLUE = RGBColor(0x18, 0x90, 0xff)
INK_WARM = RGBColor(0xff, 0x59, 0x40)
INK_LIGHT = RGBColor(0xf5, 0xf5, 0xf5)
INK_GRAY = RGBColor(0x66, 0x66, 0x66)
WHITE = RGBColor(0xff, 0xff, 0xff)
BG_DARK = RGBColor(0x0f, 0x0f, 0x1a)
BG_CARD = RGBColor(0x1e, 0x1e, 0x2e)

def add_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color

def add_textbox(slide, left, top, width, height, text, font_size=18, color=INK_DARK, bold=False, alignment=PP_ALIGN.LEFT, font_name='Microsoft YaHei'):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = alignment
    return txBox

def add_shape(slide, shape_type, left, top, width, height, fill_color=None, line_color=None):
    shape = slide.shapes.add_shape(shape_type, Inches(left), Inches(top), Inches(width), Inches(height))
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()
    if line_color:
        shape.line.color.rgb = line_color
    else:
        shape.line.fill.background()
    return shape

def add_card(slide, left, top, width, height, title, body, accent_color=INK_ACCENT):
    card = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height, BG_CARD)
    card.line.fill.background()
    # accent bar
    bar = add_shape(slide, MSO_SHAPE.RECTANGLE, left, top, Inches(0.08), height, accent_color)
    # title
    add_textbox(slide, left + 0.3, top + 0.2, width - 0.5, 0.5, title, 16, WHITE, True)
    # body
    add_textbox(slide, left + 0.3, top + 0.8, width - 0.5, height - 1.0, body, 12, RGBColor(0xcc, 0xcc, 0xcc))

def add_footer(slide, page_num, total=18):
    add_textbox(slide, 0.5, 7.0, 4, 0.4, "墨锻工坊 · 微信公众号自动化发布系统", 10, INK_GRAY)
    add_textbox(slide, 11.5, 7.0, 1.5, 0.4, f"{page_num} / {total}", 10, INK_GRAY, alignment=PP_ALIGN.RIGHT)

# ════════════════════════════════════════════
# 第 1 页 | 封面
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, BG_DARK)
# 装饰线
add_shape(slide, MSO_SHAPE.RECTANGLE, 0, Inches(3.2), Inches(13.333), Inches(0.04), INK_ACCENT)
# 主标题
add_textbox(slide, 1, 1.5, 11, 1.5, "墨锻工坊", 54, WHITE, True, PP_ALIGN.CENTER)
# 副标题
add_textbox(slide, 1, 3.5, 11, 0.8, "从选题到推送，全程自动化的微信公众号内容生产系统", 22, INK_ACCENT, False, PP_ALIGN.CENTER)
# 描述
add_textbox(slide, 1, 4.5, 11, 0.6, "2 分钟搞定一篇高质量文章 · 效率提升 48 倍", 16, RGBColor(0x99, 0x99, 0x99), False, PP_ALIGN.CENTER)
# 底部
add_textbox(slide, 1, 6.0, 11, 0.5, "2026 年 10 月", 14, INK_GRAY, False, PP_ALIGN.CENTER)

# ════════════════════════════════════════════
# 第 2 页 | 项目背景：七大痛点
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "项目背景：内容创作者的七大痛点", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

pains = [
    ("灵感枯竭", "每天想选题、查资料，耗尽精力却写不出几篇"),
    ("写稿慢", "人工写一篇 2000 字需要 3-4 小时，一周最多 3-4 篇"),
    ("排版麻烦", "在编辑器和编辑软件之间来回切换，调整格式花半天"),
    ("封面对齐难", "用 PS 或在线工具做封面，尺寸不对、字体不统一"),
    ("发布繁琐", "选题→写稿→排版→预览→推送，每步都要人工操作"),
    ("质量不稳定", "自己写有时发挥失常，外包又怕质量差"),
    ("多账号难管理", "多个账号来回切换，嫌麻烦"),
]
for i, (title, desc) in enumerate(pains):
    y = 1.4 + i * 0.75
    add_textbox(slide, 0.7, y, 0.4, 0.4, f"{i+1}", 16, INK_ACCENT, True)
    add_textbox(slide, 1.2, y, 3, 0.4, title, 16, INK_DARK, True)
    add_textbox(slide, 4.5, y, 8, 0.4, desc, 14, INK_GRAY)
add_footer(slide, 2)

# ════════════════════════════════════════════
# 第 3 页 | 解决方案
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, BG_DARK)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "解决方案：一条全自动流水线", 32, WHITE, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

# 流水线
steps = ["选题", "写稿", "排版", "封面", "推送"]
for i, step in enumerate(steps):
    x = 0.8 + i * 2.5
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(1.6), Inches(2), Inches(0.8), INK_ACCENT)
    add_textbox(slide, x, Inches(1.7), Inches(2), 0.6, step, 20, WHITE, True, PP_ALIGN.CENTER)
    if i < len(steps) - 1:
        add_textbox(slide, x + 2.0, Inches(1.7), 0.5, 0.6, "→", 24, INK_GRAY, True, PP_ALIGN.CENTER)

# 对比表格
add_textbox(slide, 0.5, 2.8, 12, 0.5, "核心数据对比", 20, WHITE, True)
headers = ["维度", "人工运营", "使用本系统"]
col_widths = [3, 4, 4]
for i, h in enumerate(headers):
    x = 0.8 + sum(col_widths[:i])
    add_textbox(slide, x, 3.4, col_widths[i], 0.4, h, 14, INK_ACCENT, True)

rows = [
    ("每周产出", "3-4 篇", "20-30 篇，没有上限"),
    ("单篇耗时", "4 小时", "5 分钟"),
    ("排版成本", "30 分钟/篇", "自动完成"),
    ("封面制作", "30 分钟/张", "3 秒/张"),
    ("发布流程", "人工 5 步骤", "一键全自动"),
]
for i, (dim, before, after) in enumerate(rows):
    y = 3.9 + i * 0.55
    add_textbox(slide, 0.8, y, 3, 0.4, dim, 13, WHITE, True)
    add_textbox(slide, 3.8, y, 4, 0.4, before, 13, RGBColor(0x99, 0x99, 0x99))
    add_textbox(slide, 7.8, y, 4, 0.4, after, 13, INK_ACCENT, True)

add_textbox(slide, 0.5, 6.8, 12, 0.5, "效率提升 48 倍", 24, INK_ACCENT, True, PP_ALIGN.CENTER)
add_footer(slide, 3)

# ════════════════════════════════════════════
# 第 4 页 | 项目定位与适用人群
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "项目定位与适用人群", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

add_textbox(slide, 0.5, 1.3, 12, 0.5, "本地化部署 · 数据私有 · 不依赖任何第三方云服务", 16, INK_BLUE, True)

audiences = [
    ("企业自媒体", "需要高频发布，保持内容更新频率"),
    ("自媒体工作室", "运营多个账号，需要批量生产内容"),
    ("个人博主", "时间有限，但想保持稳定的发布节奏"),
    ("营销团队", "需要快速产出行业热点内容"),
    ("创业公司", "预算有限，无法雇佣专业内容团队"),
]
for i, (title, desc) in enumerate(audiences):
    y = 2.0 + i * 0.9
    add_shape(slide, MSO_SHAPE.OVAL, 0.7, y + 0.1, 0.3, 0.3, INK_ACCENT)
    add_textbox(slide, 1.2, y, 3, 0.4, title, 16, INK_DARK, True)
    add_textbox(slide, 4.5, y, 8, 0.4, desc, 14, INK_GRAY)
add_footer(slide, 4)

# ════════════════════════════════════════════
# 第 5 页 | 技术架构总览
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, BG_DARK)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "技术架构总览", 32, WHITE, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

layers = [
    ("Web 可视化界面层", "Flask + 原生 HTML/JS/CSS", INK_BLUE),
    ("业务逻辑层", "选题 │ 写稿 │ 排版 │ 封面 │ 发布 │ 定时任务", INK_ACCENT),
    ("AI 能力层", "DeepSeek │ OpenAI │ 通义千问 │ Ollama", INK_WARM),
    ("数据存储层", "SQLite（用户/账号/文章/配置）", RGBColor(0x99, 0x99, 0x99)),
]
for i, (title, desc, color) in enumerate(layers):
    y = 1.5 + i * 1.2
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 1, y, 11, 0.9, BG_CARD)
    add_shape(slide, MSO_SHAPE.RECTANGLE, 1, y, Inches(0.08), Inches(0.9), color)
    add_textbox(slide, 1.3, y + 0.1, 4, 0.4, title, 16, WHITE, True)
    add_textbox(slide, 5.5, y + 0.15, 6, 0.4, desc, 14, RGBColor(0xcc, 0xcc, 0xcc))

add_textbox(slide, 0.5, 6.3, 12, 0.5, "Python 生态完善 · Flask 轻量单进程 · SQLite 零配置即备份", 14, INK_GRAY, False, PP_ALIGN.CENTER)
add_footer(slide, 5)

# ════════════════════════════════════════════
# 第 6 页 | 核心模块：智能选题
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "核心模块拆解（一）：智能选题", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

features = [
    ("多源数据采集", "RSS 订阅 + 网页爬取 + Bing Search + DuckDuckGo"),
    ("8 大领域支持", "科技、汽车、财经、美食、育儿、健康、旅游、其他"),
    ("AI 评分排序", "0-10 分多维度评分，自动排序"),
    ("智能决策", "≥8.0 生成 3 篇，≥7.0 生成 2 篇，≥6.0 生成 1 篇"),
    ("缓存机制", "选题结果缓存 6 小时，避免重复抓取"),
]
for i, (title, desc) in enumerate(features):
    y = 1.5 + i * 0.9
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.7, y, 11.5, 0.7, INK_LIGHT)
    add_textbox(slide, 1.0, y + 0.1, 3.5, 0.4, title, 15, INK_DARK, True)
    add_textbox(slide, 4.8, y + 0.1, 7, 0.4, desc, 13, INK_GRAY)

add_textbox(slide, 0.5, 6.2, 12, 0.5, "auto_selector.py — 从「找半天」到「1 分钟获取 10 个高质量选题」", 14, INK_BLUE, True, PP_ALIGN.CENTER)
add_footer(slide, 6)

# ════════════════════════════════════════════
# 第 7 页 | 核心模块：AI 写作
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "核心模块拆解（二）：AI 写作", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

# 降级链
add_textbox(slide, 0.5, 1.3, 12, 0.4, "四级自动降级，确保任何环境可用", 16, INK_BLUE, True)
chain = ["数据库默认模型", "config.json", "环境变量", "Ollama 本地", "内置模板"]
for i, item in enumerate(chain):
    x = 0.5 + i * 2.5
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(1.8), Inches(2.2), Inches(0.5), INK_LIGHT)
    add_textbox(slide, x, Inches(1.85), Inches(2.2), 0.4, item, 12, INK_DARK, True, PP_ALIGN.CENTER)
    if i < len(chain) - 1:
        add_textbox(slide, x + 2.2, Inches(1.85), 0.3, 0.4, "→", 16, INK_ACCENT, True, PP_ALIGN.CENTER)

features = [
    ("多模型支持", "DeepSeek、OpenAI、通义千问、Moonshot、智谱 AI、本地 Ollama"),
    ("去 AI 味儿", "内置专业写作提示词，模仿真人写稿风格"),
    ("爆款标题", "基于好奇心缺口、损失厌恶、社会认同等心理学原理"),
    ("AI 排版优化", "自动优化文章结构和表达"),
    ("多篇文章", "一次选题可生成 1-3 篇不同角度的文章"),
]
for i, (title, desc) in enumerate(features):
    y = 2.6 + i * 0.8
    add_textbox(slide, 0.7, y, 3, 0.4, title, 14, INK_DARK, True)
    add_textbox(slide, 4.0, y, 8.5, 0.4, desc, 13, INK_GRAY)
add_footer(slide, 7)

# ════════════════════════════════════════════
# 第 8 页 | 核心模块：排版引擎
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "核心模块拆解（三）：排版引擎", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

add_textbox(slide, 0.5, 1.3, 12, 0.4, "解决微信公众号排版最大痛点 — 微信不支持外链 CSS", 16, INK_BLUE, True)

# 技术方案
add_textbox(slide, 0.5, 1.8, 12, 0.4, "技术方案", 16, INK_DARK, True)
steps = [
    ("1. Markdown 解析", "使用 mistune v3 解析"),
    ("2. CSS 内联", "使用 premailer 内联到每个标签"),
    ("3. 输出 HTML", "微信可直接粘贴/提交"),
]
for i, (title, desc) in enumerate(steps):
    x = 0.5 + i * 4
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(2.3), Inches(3.5), Inches(0.8), INK_LIGHT)
    add_textbox(slide, x + 0.2, Inches(2.4), 3, 0.3, title, 14, INK_DARK, True)
    add_textbox(slide, x + 0.2, Inches(2.7), 3, 0.3, desc, 12, INK_GRAY)

# 模板
add_textbox(slide, 0.5, 3.4, 12, 0.4, "五套排版模板", 16, INK_DARK, True)
templates = [
    ("经典", "左边框竖线 + 简洁干净", "通用"),
    ("杂志", "居中标题 + 底部分割线", "生活、文化"),
    ("科技", "背景色块 + 引用块图标感", "科技、互联网"),
    ("极简", "大量留白 + 细线分割", "观点、评论"),
    ("笔记本", "手写风格 + 虚线边框", "个人、随笔"),
]
for i, (name, style, usage) in enumerate(templates):
    x = 0.5 + i * 2.5
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(3.9), Inches(2.3), Inches(1.2), BG_CARD)
    add_textbox(slide, x + 0.15, Inches(4.0), 2, 0.3, name, 14, INK_ACCENT, True)
    add_textbox(slide, x + 0.15, Inches(4.35), 2, 0.3, style, 11, WHITE)
    add_textbox(slide, x + 0.15, Inches(4.7), 2, 0.3, usage, 11, INK_GRAY)

add_textbox(slide, 0.5, 5.5, 12, 0.5, "md_converter.py — 从「30 分钟调整」到「自动完成」", 14, INK_BLUE, True, PP_ALIGN.CENTER)
add_footer(slide, 8)

# ════════════════════════════════════════════
# 第 9 页 | 核心模块：封面生成
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "核心模块拆解（四）：封面生成", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

# 规格
specs = [
    ("尺寸", "900 × 383 px（微信标准 2.35:1）"),
    ("格式", "JPG / PNG，< 5MB"),
    ("AI 模式", "调用 WorkBuddy image_gen 生成 AI 封面"),
    ("本地模式", "Pillow 生成纯色+文字封面（无需网络）"),
]
for i, (title, desc) in enumerate(specs):
    y = 1.5 + i * 0.7
    add_textbox(slide, 0.7, y, 2.5, 0.4, title, 15, INK_DARK, True)
    add_textbox(slide, 3.5, y, 9, 0.4, desc, 14, INK_GRAY)

# 四种主题
add_textbox(slide, 0.5, 4.5, 12, 0.4, "四种主题配色", 16, INK_DARK, True)
themes = [
    ("绿色", "微信绿", RGBColor(0x07, 0xc1, 0x60)),
    ("深色", "暗黑风", RGBColor(0x1e, 0x1e, 0x2e)),
    ("科技蓝", "专业蓝", RGBColor(0x18, 0x90, 0xff)),
    ("暖色", "活力橙", RGBColor(0xff, 0x59, 0x40)),
]
for i, (name, desc, color) in enumerate(themes):
    x = 0.5 + i * 3
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(5.0), Inches(2.5), Inches(0.8), color)
    add_textbox(slide, x + 0.2, Inches(5.1), 2, 0.3, name, 14, WHITE, True)
    add_textbox(slide, x + 0.2, Inches(5.45), 2, 0.3, desc, 11, WHITE)

add_textbox(slide, 0.5, 6.2, 12, 0.5, "cover_generator.py — 从「30 分钟/张」到「3 秒/张」", 14, INK_BLUE, True, PP_ALIGN.CENTER)
add_footer(slide, 9)

# ════════════════════════════════════════════
# 第 10 页 | 核心模块：微信发布
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "核心模块拆解（五）：微信发布", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

# 发布流程
add_textbox(slide, 0.5, 1.3, 12, 0.4, "完整对接微信公众号 API", 16, INK_BLUE, True)
flow = [
    "access_token 获取与缓存（2小时有效期）",
    "永久素材上传（封面图）",
    "草稿创建（draft/add）",
    "提交发布（freepublish/submit）",
    "查询发布状态（freepublish/get）",
]
for i, step in enumerate(flow):
    y = 1.9 + i * 0.6
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.7, y, 11.5, 0.45, INK_LIGHT)
    add_textbox(slide, 1.0, y + 0.05, 11, 0.35, f"Step {i+1}: {step}", 13, INK_DARK)

# 安全设计
add_textbox(slide, 0.5, 5.2, 12, 0.4, "安全设计", 16, INK_DARK, True)
safety = [
    "默认推送到草稿箱，保留人工审核环节",
    "access_token 自动缓存，避免频繁请求",
    "完整的错误处理和重试机制",
]
for i, item in enumerate(safety):
    add_textbox(slide, 0.7, 5.7 + i * 0.4, 11, 0.35, f"• {item}", 13, INK_GRAY)
add_footer(slide, 10)

# ════════════════════════════════════════════
# 第 11 页 | 核心模块：链接改写
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "核心模块拆解（六）：链接改写", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

add_textbox(slide, 0.5, 1.3, 12, 0.4, "五步流水线，把任意网页内容转化为原创公众号文章", 16, INK_BLUE, True)

steps = [
    ("Step 1", "提取链接内容", "requests + Playwright 降级"),
    ("Step 2", "AI 观点提取", "分析风格 + 摘要 + 核心观点"),
    ("Step 3", "AI 文章仿写", "基于观点和摘要重新创作"),
    ("Step 4", "爆款标题生成", "统一使用 title_generator 模块"),
    ("Step 5", "文章排版", "Markdown → 公众号格式 HTML"),
]
for i, (step, title, desc) in enumerate(steps):
    y = 1.9 + i * 0.85
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.7, y, 11.5, 0.7, INK_LIGHT)
    add_textbox(slide, 1.0, y + 0.05, 1.2, 0.3, step, 12, INK_ACCENT, True)
    add_textbox(slide, 2.3, y + 0.05, 3, 0.3, title, 14, INK_DARK, True)
    add_textbox(slide, 5.5, y + 0.05, 6.5, 0.3, desc, 13, INK_GRAY)

add_textbox(slide, 0.5, 6.3, 12, 0.5, "article_rewriter.py — 看到好文章，3 分钟变成自己的原创内容", 14, INK_BLUE, True, PP_ALIGN.CENTER)
add_footer(slide, 11)

# ════════════════════════════════════════════
# 第 12 页 | 数据架构设计
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, BG_DARK)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "数据架构设计", 32, WHITE, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

# 表列表
tables = [
    ("users", "用户表"),
    ("sessions", "登录会话"),
    ("accounts", "公众号账号"),
    ("articles", "历史文章"),
    ("scheduled_tasks", "定时任务"),
    ("scheduled_task_runs", "任务执行记录"),
    ("domains", "领域分类"),
    ("ai_models", "AI 大模型配置"),
    ("cover_generations", "封面生成记录"),
    ("material_groups", "素材分组"),
    ("material_library", "素材库"),
]
for i, (table, desc) in enumerate(tables):
    col = i % 3
    row = i // 3
    x = 0.5 + col * 4.2
    y = 1.5 + row * 0.8
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, Inches(3.8), Inches(0.6), BG_CARD)
    add_textbox(slide, x + 0.2, y + 0.05, 3.5, 0.3, table, 13, INK_ACCENT, True)
    add_textbox(slide, x + 0.2, y + 0.32, 3.5, 0.25, desc, 11, RGBColor(0xcc, 0xcc, 0xcc))

# 多用户隔离
add_textbox(slide, 0.5, 5.5, 12, 0.4, "多用户隔离", 16, WHITE, True)
add_textbox(slide, 0.5, 6.0, 12, 0.4, "每个用户只能访问自己的数据，支持团队协作", 14, RGBColor(0xcc, 0xcc, 0xcc))
add_textbox(slide, 0.5, 6.5, 12, 0.4, "打包后数据目录：macOS ~/Library/Application Support/WeChatPublisher/", 12, INK_GRAY)
add_footer(slide, 12)

# ════════════════════════════════════════════
# 第 13 页 | 应用场景一：全自动发布
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "应用场景一：全自动发布", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

add_textbox(slide, 0.5, 1.3, 12, 0.4, "最适合：想要节省时间、自动生成和发布内容的用户", 16, INK_BLUE, True)

# 操作步骤
add_textbox(slide, 0.5, 1.8, 12, 0.4, "操作流程", 16, INK_DARK, True)
steps = [
    "进入「工作台」页面",
    "点击「全自动发布」按钮",
    "系统自动执行：选题 → 写稿（1-3 篇）→ 预览 → 推送",
    "查看执行日志",
]
for i, step in enumerate(steps):
    y = 2.3 + i * 0.55
    add_shape(slide, MSO_SHAPE.OVAL, 0.7, y + 0.05, 0.35, 0.35, INK_ACCENT)
    add_textbox(slide, 1.2, y, 11, 0.4, f"{i+1}. {step}", 14, INK_DARK)

# 最佳实践
add_textbox(slide, 0.5, 4.8, 12, 0.4, "最佳实践", 16, INK_DARK, True)
practices = [
    "设置定时任务：每天 9:00 自动运行",
    "周一设置一次，一周内容自动完成",
    "每天早上打开公众号，直接审核发布即可",
]
for i, item in enumerate(practices):
    add_textbox(slide, 0.7, 5.3 + i * 0.45, 11, 0.4, f"• {item}", 14, INK_GRAY)
add_footer(slide, 13)

# ════════════════════════════════════════════
# 第 14 页 | 应用场景二：精准选题写稿
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "应用场景二：精准选题写稿", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

add_textbox(slide, 0.5, 1.3, 12, 0.4, "最适合：对选题有特殊要求，需要精准控制的用户", 16, INK_BLUE, True)

# 操作步骤
add_textbox(slide, 0.5, 1.8, 12, 0.4, "操作流程", 16, INK_DARK, True)
steps = [
    "进入「自动选题」页面",
    "点击「获取选题」获取最新热点",
    "查看 AI 评分和选题描述",
    "选中一个选题，点击「AI 生成文章」",
    "在预览页面查看效果",
    "（可选）手动编辑文章内容",
    "点击「推送到草稿箱」",
]
for i, step in enumerate(steps):
    y = 2.3 + i * 0.5
    add_shape(slide, MSO_SHAPE.OVAL, 0.7, y + 0.05, 0.3, 0.3, INK_ACCENT)
    add_textbox(slide, 1.2, y, 11, 0.35, f"{i+1}. {step}", 13, INK_DARK)

add_textbox(slide, 0.5, 6.0, 12, 0.5, "数据驱动：不再靠「感觉」选题，AI 评分帮你快速判断选题质量", 14, INK_BLUE, True, PP_ALIGN.CENTER)
add_footer(slide, 14)

# ════════════════════════════════════════════
# 第 15 页 | 应用场景三：一键排版 + 定时任务
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "应用场景三：一键排版 + 定时任务", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

# 左列：一键排版
add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.5, 1.4, Inches(5.8), Inches(5.2), INK_LIGHT)
add_textbox(slide, 0.8, 1.6, 5, 0.4, "一键排版", 18, INK_DARK, True)
add_textbox(slide, 0.8, 2.1, 5, 0.3, "适合：已有优质内容，想要快速复用", 13, INK_GRAY)
items = [
    "粘贴网页或文档内容（支持任意格式）",
    "自动识别标题/段落",
    "AI 智能排版优化",
    "3 分钟完成从粘贴到发布",
]
for i, item in enumerate(items):
    add_textbox(slide, 0.8, 2.6 + i * 0.5, 5, 0.4, f"• {item}", 13, INK_DARK)

# 右列：定时任务
add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 6.8, 1.4, Inches(5.8), Inches(5.2), INK_LIGHT)
add_textbox(slide, 7.1, 1.6, 5, 0.4, "定时任务", 18, INK_DARK, True)
add_textbox(slide, 7.1, 2.1, 5, 0.3, "适合：需要自动化批量发布的用户", 13, INK_GRAY)
items = [
    "支持串行/并行两种执行模式",
    "执行历史完整记录",
    "SSE 实时日志推送",
    "失败自动重试",
]
for i, item in enumerate(items):
    add_textbox(slide, 7.1, 2.6 + i * 0.5, 5, 0.4, f"• {item}", 13, INK_DARK)

add_footer(slide, 15)

# ════════════════════════════════════════════
# 第 16 页 | 创新点总结
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, BG_DARK)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "创新点总结", 32, WHITE, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

innovations = [
    ("AI 评分驱动选题", "不是简单的关键词匹配，而是基于 AI 对每条选题进行多维度评分，自动决定生成多少篇文章"),
    ("多模型自动降级", "支持 5 种 LLM 后端，按优先级自动切换，确保任何环境下都能工作"),
    ("去 AI 味儿引擎", "内置专业写作提示词，基于心理学原理（好奇心缺口、损失厌恶、社会认同）生成标题和内容"),
    ("全链路自动化", "从选题到推送，5 个环节全部自动化，中间不需要任何人工干预"),
    ("本地化 + 数据私有", "所有数据存储在本地 SQLite 中，不依赖任何第三方云服务，数据完全可控"),
]
for i, (title, desc) in enumerate(innovations):
    y = 1.5 + i * 1.0
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.5, y, Inches(12), Inches(0.8), BG_CARD)
    add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, y, Inches(0.08), Inches(0.8), INK_ACCENT)
    add_textbox(slide, 0.8, y + 0.05, 3.5, 0.35, f"{i+1}. {title}", 15, WHITE, True)
    add_textbox(slide, 4.5, y + 0.1, 8, 0.35, desc, 12, RGBColor(0xcc, 0xcc, 0xcc))
add_footer(slide, 16)

# ════════════════════════════════════════════
# 第 17 页 | 项目数据与成果
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, WHITE)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "项目数据与成果", 32, INK_DARK, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

stats = [
    ("15+", "核心代码模块"),
    ("11", "数据库表"),
    ("5+", "支持 AI 模型"),
    ("5", "排版模板"),
    ("4", "封面主题"),
    ("8", "支持领域"),
    ("14", "热搜数据源"),
    ("5 分钟", "单篇耗时"),
    ("48 倍", "效率提升"),
]
for i, (num, label) in enumerate(stats):
    col = i % 3
    row = i // 3
    x = 0.5 + col * 4.2
    y = 1.5 + row * 1.5
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, Inches(3.8), Inches(1.2), INK_LIGHT)
    add_textbox(slide, x, y + 0.15, 3.8, 0.6, num, 36, INK_ACCENT, True, PP_ALIGN.CENTER)
    add_textbox(slide, x, y + 0.75, 3.8, 0.35, label, 14, INK_GRAY, False, PP_ALIGN.CENTER)
add_footer(slide, 17)

# ════════════════════════════════════════════
# 第 18 页 | 总结与展望
# ════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, BG_DARK)
add_textbox(slide, 0.5, 0.3, 12, 0.8, "总结与展望", 32, WHITE, True)
add_shape(slide, MSO_SHAPE.RECTANGLE, 0.5, Inches(1.1), Inches(2), Inches(0.04), INK_ACCENT)

# 总结
add_textbox(slide, 0.5, 1.4, 12, 0.4, "总结", 18, INK_ACCENT, True)
summary = [
    "技术栈成熟 — Python + Flask + SQLite，稳定可靠",
    "功能完整 — 覆盖选题、写作、排版、封面、发布全链路",
    "AI 深度集成 — 多模型支持，去 AI 味儿，爆款标题",
    "数据私有 — 本地化部署，数据安全可控",
    "开箱即用 — 支持 macOS/Windows 桌面打包",
]
for i, item in enumerate(summary):
    add_textbox(slide, 0.7, 1.9 + i * 0.5, 11, 0.4, f"• {item}", 14, RGBColor(0xcc, 0xcc, 0xcc))

# 未来规划
add_textbox(slide, 0.5, 4.6, 12, 0.4, "未来规划", 18, INK_ACCENT, True)
future = [
    "支持更多内容平台（小红书、抖音、知乎）",
    "素材库 AI 智能推荐",
    "团队协作与权限管理",
    "数据分析与爆款预测",
]
for i, item in enumerate(future):
    add_textbox(slide, 0.7, 5.1 + i * 0.45, 11, 0.4, f"• {item}", 14, RGBColor(0xcc, 0xcc, 0xcc))

add_textbox(slide, 0.5, 6.8, 12, 0.5, "感谢聆听！ Q & A", 20, WHITE, True, PP_ALIGN.CENTER)

# ════════════════════════════════════════════
# 保存
# ════════════════════════════════════════════
output_path = "/Users/casey/workspace/inkForge-studio/墨锻工坊.pptx"
prs.save(output_path)
print(f"PPT 已生成：{output_path}")
print(f"共 {len(prs.slides)} 页")
