"""
article_rewriter.py
链接改写模块（V2 — 五步流水线版）

流程：
  Step 1: 提取链接内容（抓取 URL → 纯文本正文）
  Step 2: AI 观点提取（分析风格 + 摘要 + 核心观点）
  Step 3: AI 文章仿写（基于观点和摘要重新创作）
  Step 4: AI 爆款标题生成（统一使用 title_generator 模块）
  Step 5: 文章排版（Markdown → 通用格式 HTML，内联 CSS + span 着色）

调用入口：rewrite_article_v2()
"""

import re
import json
import time
import requests
from typing import Tuple, Optional, Dict, List
from urllib.parse import urlparse

try:
    from readability.readability import Document as ReadabilityDoc
    from readability.readability import Unparseable
    HAS_READABILITY = True
except ImportError:
    HAS_READABILITY = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

from .ai_writer import _detect_llm_backend, _call_openai, _call_ollama
from .title_generator import TITLE_GEN_PROMPT, generate_title as _generate_title_v2


# ════════════════════════════════════════════════════════════
# Step 1: URL 内容抓取（复用原有逻辑）
# ════════════════════════════════════════════════════════════

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

def _parse_content_title(content: str) -> Tuple[str, str]:
    """从用户粘贴的内容中提取标题和正文。第一行作为标题（去掉 # 前缀），其余作为正文。"""
    lines = content.strip().split('\n')
    title = ''
    body_start = 0

    if lines:
        first_line = lines[0].strip()
        # 去掉 Markdown 标题前缀 # ## ### 等
        clean_first = re.sub(r'^#+\s*', '', first_line)
        if clean_first and len(clean_first) < 100:
            title = clean_first
            body_start = 1

    body = '\n'.join(lines[body_start:]).strip()
    return title or '未命名文章', body


_BLOCKED_DOMAINS = set()


def fetch_url_content(url: str, timeout: int = 15) -> Tuple[str, str]:
    """抓取 URL 页面，提取纯文本正文和标题。Returns: (title, content_text)"""
    url = url.strip()
    if not url:
        raise ValueError("URL 不能为空")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    for blocked in _BLOCKED_DOMAINS:
        if blocked in domain:
            raise ValueError(f"不支持抓取 {blocked} 的内容")

    print(f"   [fetch] 正在抓取：{url}")

    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()

    if resp.encoding and resp.encoding.lower() not in ("utf-8", "utf8"):
        resp.encoding = "utf-8"

    html = resp.text
    title = ""
    content_text = ""

    if HAS_READABILITY:
        try:
            doc = ReadabilityDoc(html)
            summary = doc.summary()
            title = doc.title() or ""
            if HAS_BS4:
                soup = BeautifulSoup(summary, "html.parser")
                content_text = soup.get_text(separator="\n", strip=True)
            else:
                content_text = re.sub(r"<[^>]+>", " ", summary)
                content_text = re.sub(r"\s+", " ", content_text).strip()
        except Unparseable:
            title, content_text = _extract_with_bs4(html)
        except Exception as e:
            print(f"   [fetch] readability 解析失败：{e}，降级处理")
            title, content_text = _extract_with_bs4(html)
    elif HAS_BS4:
        title, content_text = _extract_with_bs4(html)
    else:
        title, content_text = _extract_with_regex(html)

    title = title.strip().replace("\n", " ")
    content_text = _clean_text(content_text)

    if not content_text:
        raise ValueError("未能提取到文章正文内容")

    print(f"   [fetch] 提取成功：标题「{title[:40]}」，正文 {len(content_text)} 字")
    return title, content_text


def _extract_with_bs4(html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside",
                     "iframe", "noscript", "form", "button"]):
        tag.decompose()

    title = ""
    title_tag = soup.find("h1") or soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    article = (
        soup.find("article")
        or soup.find("div", class_=re.compile(r"article|content|post|entry|story", re.I))
        or soup.find("div", class_=re.compile(r"rich_media_content"))
        or soup.find(id=re.compile(r"article|content|post|entry", re.I))
        or soup.body
    )

    if article:
        content_text = article.get_text(separator="\n", strip=True)
    else:
        content_text = soup.get_text(separator="\n", strip=True)

    return title, content_text


def _extract_with_regex(html: str) -> Tuple[str, str]:
    title_m = re.search(r"<title[^>]*>([^<]{2,100})</title>", html, re.I)
    title = title_m.group(1).strip() if title_m else ""

    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text).strip()

    return title, text


def _clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    lines = [line for line in text.split("\n") if len(line) > 5]
    text = "\n".join(lines)

    if len(text) > 8000:
        text = text[:8000] + "\n\n（文章过长，已截断）"

    return text.strip()


# ════════════════════════════════════════════════════════════
# Step 2: AI 观点提取
# ════════════════════════════════════════════════════════════

_ANALYZE_PROMPT = """# 角色
你是一个专业的文章分析及仿写助手，能够精准分析文章的风格和写作方式，准确提取文章核心观点。

## 技能
### 技能 1: 分析文章
1. 当用户提供一篇文章内容时，仔细研读文章，分析其整体风格，包括语言风格（如正式、幽默、文艺等）、叙事风格（如顺叙、倒叙、插叙等）以及写作手法（如举例论证、对比等）。
2. 对文章内容进行精炼概括，提取关键信息，形成文章摘要，要求涵盖文章主要情节或论述要点。
3. 提炼文章所传达的核心观点，即文章想要表达的主要思想或主旨。
4. 以如下格式输出分析结果：
    - 文章风格：[具体风格描述]
    - 文章摘要：[精炼的文章内容概括]
    - 核心观点：[文章的核心思想或主旨]

## 限制:
- 只围绕文章的分析和仿写展开工作，拒绝回答与该任务无关的话题。
- 分析结果的输出内容需逻辑清晰、表达准确。
- 文章摘要应简洁明了，不超过 200 字。
- 核心观点的表述应精准，不超过 100 字。"""


def _call_llm(prompt: str, user_id: int = None):
    """统一调用 LLM 的封装。返回 (backend_name, response_text)"""
    backend, config = _detect_llm_backend(user_id)

    if backend == "template":
        raise RuntimeError("未配置 AI 模型，无法使用改写功能。请在系统配置中添加 AI 模型。")

    if backend == "openai":
        result = _call_openai(prompt, config)
    elif backend == "ollama":
        result = _call_ollama(prompt, config)
    else:
        raise RuntimeError(f"不支持的 AI 后端：{backend}")

    return backend, result


def analyze_article(title: str, content: str, user_id: int = None) -> Dict[str, str]:
    """
    Step 2: AI 分析原文，提取风格、摘要、核心观点。

    Returns:
        {"style": "...", "summary": "...", "core_viewpoint": "..."}
    """
    prompt = f"""{_ANALYZE_PROMPT}

## 待分析的原文

### 标题
{title}

### 正文内容
{content}

请按上述格式输出分析结果：
"""

    print(f"   [step2] 正在分析文章观点...")
    backend, result = _call_llm(prompt, user_id)
    result = result.strip()

    # 解析输出
    analysis = {"style": "", "summary": "", "core_viewpoint": ""}

    style_m = re.search(r'文章风格[：:]\s*(.+?)(?:\n|$)', result)
    summary_m = re.search(r'文章摘要[：:]\s*(.+?)(?:\n|$)', result)
    viewpoint_m = re.search(r'核心观点[：:]\s*(.+?)(?:\n|$)', result)

    analysis["style"] = style_m.group(1).strip() if style_m else "观点评论"
    analysis["summary"] = summary_m.group(1).strip() if summary_m else content[:200]
    analysis["core_viewpoint"] = viewpoint_m.group(1).strip() if viewpoint_m else title

    print(f"   [step2] 观点提取完成 → 风格:{analysis['style'][:20]}, 观点:{analysis['core_viewpoint'][:30]}...")
    return analysis


# ════════════════════════════════════════════════════════════
# Step 3: AI 文章仿写
# ════════════════════════════════════════════════════════════

_REWRITE_V2_PROMPT = """# 角色
你是一个专业的文章创作者，擅长根据用户需求创作出吸引人的爆文。能够精准把握各种写作风格，围绕核心观点展开创作，并结合内容摘要丰富文章内容，同时满足用户提出的额外要求。

## 技能
### 技能 1: 创作文章
1.根据用户提供的标题和观点信息进行创作，文章不少于2000字
2.深度思考后，构思主题、大纲和内容
3.创作符合风格和要求的文章，观点一定要独到
4.完成文章后，自行审稿和修改润色
5.最后直接输出文章正文内容，不需要输出标题。

## 文章风格
1.作者日常观点论述文章，注意文章开头技巧（开篇、调动读者情绪、激发引导读者思考），引发读者阅读兴趣。
2.开门见山，提出主题和观点，着重引发读者的情感共鸣，以情动人，让读者在阅读中产生强烈的情感体验;
3.语言风格：个人深度思考风格，简洁的日常表达方式
4.长短句组合，短句使语言简洁、明快，整句散句结合使语言错落有致，丰富文章的层次和可读性;
5.段落转折连接，避免使用：首先、其次、最后、总而言之、总之等逻辑连接词，不要使用"繁杂的世界，快节奏的世界，充满变化的世界里"等虚无的形容词。杜绝AI味道

## 内容格式：
1.使用Markdown语法风格，区分一级、二级、三级标题使用标签"#、##、###"。
2.文中核心句子使用HTML标签包裹
<span style="color: rgb(202,88,99); font-weight: bold;" >句子</span>
3.长短句组合，避免单个句子超过3行。

## 限制:
- 只围绕用户提供的写作风格、核心观点、内容摘要以及额外要求创作文章，拒绝回答与文章创作无关的话题。
- 所输出的文章内容必须符合正常的语言表达和逻辑要求。
- 禁止使用和出现英文、单词。
- 文章须严格遵循不少于2000字的字数要求,控制篇幅,做到详略得当,避免内容单薄。
- 杜绝任何抄袭、剽窃等侵权行为,文章内容须为原创,切勿照搬照抄他人作品。
- 严禁在文章中出现任何违反国家法律法规、社会公序良俗或影响平台形象的不当言论。
- 严格按照原文的事实，不要杜撰一些不存在的事实
"""


def rewrite_article_v2(
    original_title: str,
    original_content: str,
    analysis: Dict[str, str],
    user_id: int = None,
    extra_instructions: str = "",
) -> str:
    """
    Step 3: 基于观点分析结果，AI 仿写一篇全新的原创文章。

    Args:
        original_title: 原文标题
        original_content: 原文正文
        analysis: Step 2 返回的分析结果 {style, summary, core_viewpoint}
        user_id: 用户 ID
        extra_instructions: 额外指令

    Returns:
        Markdown 格式的仿写文章正文（不含标题，由 Step 4 单独生成）
    """
    style = analysis.get("style", "观点评论")
    summary = analysis.get("summary", "")
    core_viewpoint = analysis.get("core_viewpoint", "")

    prompt = f"""{_REWRITE_V2_PROMPT}

---

## 写作素材信息

**原标题：** {original_title}
**核心观点：** {core_viewpoint}
**内容摘要：** {summary}
**参考风格：** {style}

**原文事实参考（必须严格遵守事实，不得杜撰）：**
{original_content[:4000]}
{"（原文过长，仅展示前4000字供事实参考）" if len(original_content) > 4000 else ""}

{f"\n## 额外要求\n{extra_instructions}" if extra_instructions else ""}

请直接输出文章正文内容（不需要输出标题），使用 Markdown 格式：
"""

    print(f"   [step3] 正在仿写文章...")
    backend, result = _call_llm(prompt, user_id)
    result = result.strip()

    # 清理可能的标题前缀
    result = re.sub(r'^#\s+.+\n+', '', result, count=1)

    print(f"   [step3] 仿写完成，共 {len(result)} 字")
    return result


# ════════════════════════════════════════════════════════════
# Step 4: AI 爆款标题生成（统一使用 title_generator 模块）
# ════════════════════════════════════════════════════════════

# 向后兼容：本地别名指向统一模块的函数
generate_title = _generate_title_v2


# ════════════════════════════════════════════════════════════
# Step 5: 文章排版（Markdown → 通用格式 HTML）
# ════════════════════════════════════════════════════════════

def format_article_html(title: str, markdown_body: str) -> str:
    """
    Step 5: 将 Markdown 文章排版为带内联样式的 HTML 格式。

    处理规则：
    1. 将 # ## ### 转为带内联样式的 HTML 标签
    2. 保留 <span style="color: ..."> 已有的着色标记
    3. 段落自动加 <p> 标签并内联基础样式
    4. 输出完整的 HTML（含 section 容器 + 内联 CSS）

    Args:
        title: 文章标题
        markdown_body: Markdown 正文（Step 3 输出）

    Returns:
        完整的 HTML 字符串，可直接粘贴到编辑器
    """
    html_parts = []

    # 主标题
    html_parts.append(f'<h2 style="font-size:22px;font-weight:bold;color:#333;margin-bottom:16px;line-height:1.4;">{_escape_html(title)}</h2>')
    html_parts.append('')

    lines = markdown_body.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        # 空行跳过
        if not line:
            i += 1
            continue

        # 一级标题 #
        if line.startswith("# ") and not line.startswith("## "):
            text = line[2:].strip()
            html_parts.append(f'<section style="margin:24px 0 12px;"><h2 style="font-size:20px;font-weight:bold;color:#333;border-left:4px solid rgb(202,88,99);padding-left:12px;line-height:1.4;">{_escape_html(text)}</h2></section>')
            i += 1
            continue

        # 二级标题 ##
        if line.startswith("## ") and not line.startswith("### "):
            text = line[3:].strip()
            html_parts.append(f'<section style="margin:20px 0 10px;"><h3 style="font-size:17px;font-weight:bold;color:#444;line-height:1.4;">{_escape_html(text)}</h3></section>')
            i += 1
            continue

        # 三级标题 ###
        if line.startswith("### "):
            text = line[4:].strip()
            html_parts.append(f'<section style="margin:16px 0 8px;"><h4 style="font-size:15px;font-weight:bold;color:#555;line-height:1.4;">{_escape_html(text)}</h4></section>')
            i += 1
            continue

        # 普通段落：收集连续的非空行为一段
        paragraph_lines = []
        while i < len(lines) and lines[i].strip():
            paragraph_lines.append(lines[i].strip())
            i += 1

        para_text = " ".join(paragraph_lines)
        if para_text:
            # 将 **bold** 转为 <strong>
            para_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para_text)

            # 将已有的 <span ...> 保留（已经是 HTML），其余部分转义
            # 先把已有的 span 保护起来
            spans_found = re.findall(r'<span[^>]*>.*?</span>', para_text, re.DOTALL)
            for idx, span in enumerate(spans_found):
                para_text = para_text.replace(span, f'\x00SPAN{idx}\x00')

            para_text = _escape_html(para_text)

            # 恢复 span
            for idx, span in enumerate(spans_found):
                para_text = para_text.replace(f'\x00SPAN{idx}\x00', span)

            html_parts.append(f'<section style="margin:14px 0;line-height:1.8;font-size:15px;color:#333;text-align:justify;letter-spacing:0.5px;">{para_text}</section>')
            html_parts.append('')

    # 组装完整 HTML
    full_html = f"""<section style="max-width:100%;box-sizing:border-box;padding:4px 0;">
{''.join(html_parts)}
</section>"""

    print(f"   [step5] 排版完成，HTML 共 {len(full_html)} 字符")
    return full_html


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符（保留已有 HTML 标签的场景需要谨慎使用）"""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    # 注意这里不能替换引号，因为属性值可能用到
    return text


# ════════════════════════════════════════════════════════════
# 流水线主入口
# ════════════════════════════════════════════════════════════

def run_rewrite_pipeline(
    url: str = "",
    content: str = "",
    user_id: int = None,
    extra_instructions: str = "",
    on_step: callable = None,
) -> Dict:
    """
    执行完整的五步链接改写流水线。

    Args:
        url: 文章链接（可选，有 content 时可省略）
        content: 直接提供的文章内容（可选，优先于 url）
        user_id: 用户 ID
        extra_instructions: 额外指令
        on_step: 步骤回调函数 on_step(step_num, step_name, data) 用于报告进度

    Returns:
        {
            "original_title": str,
            "original_content": str,
            "analysis": dict,          # Step 2 结果
            "article_body": str,       # Step 3 结果 (Markdown 正文)
            "title": str,              # Step 4 结果
            "wechat_html": str,        # Step 5 结果 (完整 HTML)
        }
    """
    result = {}

    # ── Step 1: 获取内容 ──
    if on_step:
        on_step(1, "正在获取文章内容...", None)

    if content and content.strip():
        # 用户直接提供了内容，从内容中提取标题
        original_title, original_content = _parse_content_title(content)
    elif url:
        # 从链接抓取内容
        original_title, original_content = fetch_url_content(url)
    else:
        raise ValueError("请提供文章链接或文章内容")

    result["original_title"] = original_title
    result["original_content"] = original_content

    if on_step:
        on_step(1, "内容抓取完成", {
            "original_title": original_title,
            "content_length": len(original_content),
            "content_preview": original_content[:3000],
        })

    # ── Step 2: 观点提取 ──
    if on_step:
        on_step(2, "正在分析文章观点...", None)

    analysis = analyze_article(original_title, original_content, user_id)
    result["analysis"] = analysis

    if on_step:
        on_step(2, "观点提取完成", analysis)

    # ── Step 3: 文章仿写 ──
    if on_step:
        on_step(3, "正在仿写文章...", None)

    article_body = rewrite_article_v2(
        original_title=original_title,
        original_content=original_content,
        analysis=analysis,
        user_id=user_id,
        extra_instructions=extra_instructions,
    )
    result["article_body"] = article_body

    if on_step:
        on_step(3, "文章仿写完成", {
            "article_body": article_body,
            "word_count": len(article_body),
        })

    # ── Step 4: 标题生成 ──
    if on_step:
        on_step(4, "正在生成爆款标题...", None)

    title = generate_title(article_body, user_id)
    result["title"] = title

    if on_step:
        on_step(4, "标题生成完成", {"title": title, "generated_title": title})

    # ── Step 5: 排版 ──
    if on_step:
        on_step(5, "正在排版文章...", None)

    # 组装完整 Markdown（标题 + 正文），使用内置排版输出 HTML
    full_md = f"# {title}\n\n{article_body}"
    wechat_html = format_article_html(title, article_body)

    result["wechat_html"] = wechat_html

    if on_step:
        on_step(5, "排版完成", {
            "wechat_html": wechat_html,
            "html": wechat_html,
        })

    return result


# ════════════════════════════════════════════════════════════
# 兼容旧接口（保持不改）
# ════════════════════════════════════════════════════════════

def rewrite_article(
    original_title: str,
    original_content: str,
    user_id: int = None,
    word_count: int = 2000,
    style: str = "观点评论",
    custom_writing_prompt: str = "",
    extra_instructions: str = "",
) -> str:
    """旧版单步改写接口（向后兼容）"""
    backend, config = _detect_llm_backend(user_id)

    if backend == "template":
        raise RuntimeError("未配置 AI 模型，无法使用改写功能。请在系统配置中添加 AI 模型。")

    print(f"   [rewrite] 使用 {backend} 后端进行改写...")

    rewrite_prompt = f"""你是一位资深的内容创作者。现在有一篇文章，请你基于它的核心信息和事实，**完全重新写一篇原创文章**。

## 原文标题
{original_title}

## 原文内容
{original_content}

## 改写要求
1. **绝对不能抄袭**：不能用原文的原句大段照搬，必须用自己的语言重新表达
2. **严格遵照事实**：所有数据、事件、时间、人物等事实信息必须与原文一致，不能杜撰
3. **角度创新**：从不同于原文的角度切入，可以补充自己的观点和分析
4. **字数**：{word_count} 字左右
5. **风格**：{style}
6. **结构**：文章要有清晰的开头（引人入胜的钩子）、中间（层次分明的论述）、结尾（引发思考的收束）
7. **表达**：使用自然流畅的中文表达，避免AI套话，像真人写作一样
8. **禁止**：不要使用项目符号列表、表格、编号列表

{f"## 额外要求\n{extra_instructions}" if extra_instructions else ""}

{f"## 写作风格要求\n{custom_writing_prompt}" if custom_writing_prompt else ""}

请直接输出 Markdown 格式的文章，以 `# 标题` 开头。不要输出任何解释说明。"""

    if backend == "openai":
        result = _call_openai(rewrite_prompt, config)
    elif backend == "ollama":
        result = _call_ollama(rewrite_prompt, config)
    else:
        raise RuntimeError(f"不支持的 AI 后端：{backend}")

    result = result.strip()
    if not result.startswith("#"):
        result = f"# {original_title}\n\n{result}"

    print(f"   [rewrite] 改写完成，共 {len(result)} 字")
    return result
