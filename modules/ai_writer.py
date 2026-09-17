"""
ai_writer.py
AI 写文章模块 — 接收选题/提示词 → 调用 LLM → 生成完整文章 (Markdown)

支持四种 LLM 后端（按优先级自动选择）：
  1. 数据库默认 AI 模型（用户配置，优先级最高）
  2. config.json 配置（兼容旧配置）
  3. 环境变量 AI_API_KEY / AI_API_BASE
  4. 本地 Ollama（http://localhost:11434，无需 Key）
  5. 内置模板（纯离线 fallback，适合网络不可用时）
"""

import os
import json
import re
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR   = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output" / "articles"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════════
# LLM 配置检测
# ════════════════════════════════════════════════════════════

def _load_config() -> dict:
    """读取 config.json 中的配置"""
    config_path = BASE_DIR / "config.json"
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_default_ai_model_from_db(user_id: int = None) -> Optional[dict]:
    """
    从数据库获取默认 AI 模型配置

    Args:
        user_id: 用户 ID（用于多用户环境，可选）

    Returns:
        模型配置字典或 None
    """
    try:
        from modules.user_db import get_db

        with get_db() as db:
            # 如果没有指定 user_id，使用第一个用户（向后兼容）
            if user_id is None:
                # 尝试获取用户 ID 为 1 的默认模型
                model = db.get_user_default_ai_model(1)
            else:
                model = db.get_user_default_ai_model(user_id)

            if model:
                return {
                    "api_key": model["api_key"],
                    "api_base": model["api_base"] or "",
                    "model": model["model_name"],
                    "provider": model["provider"]
                }
    except Exception as e:
        print(f"   [AI] 从数据库读取模型失败：{e}")

    return None


def _detect_llm_backend(user_id: int = None) -> Tuple[str, dict]:
    """
    自动检测可用的 LLM 后端。
    优先级：数据库默认模型 > config.json > 环境变量 > Ollama 本地 > 内置模板

    Args:
        user_id: 用户 ID（用于多用户环境，可选）

    返回 (backend_name, backend_config)
    backend_name: "openai" | "ollama" | "template"
    """
    # 1. 从数据库读取默认模型（优先级最高）
    db_config = _get_default_ai_model_from_db(user_id)
    if db_config and db_config["api_key"]:
        api_key = db_config["api_key"]
        api_base = db_config["api_base"] or "https://api.openai.com/v1"
        model = db_config["model"]
        provider = db_config["provider"]
        print(f"   💡 使用数据库中的 AI 模型配置（{provider} / {model}）")
        return "openai", {"api_key": api_key, "api_base": api_base, "model": model}

    # 2. 从 config.json 读取（向后兼容）
    cfg = _load_config()
    config_key  = cfg.get("ai_api_key", "").strip()
    config_base = cfg.get("ai_api_base", "").strip()
    config_model = cfg.get("ai_model", "").strip()
    if config_key:
        api_base = config_base or "https://api.openai.com/v1"
        model    = config_model or "deepseek-chat"
        print(f"   💡 使用 config.json 中的 AI 配置（{api_base.split('/')[2]} / {model}）")
        return "openai", {"api_key": config_key, "api_base": api_base, "model": model}

    # 3. 从环境变量读取
    api_key  = os.environ.get("AI_API_KEY", "").strip()
    api_base = os.environ.get("AI_API_BASE", "https://api.openai.com/v1")
    model    = os.environ.get("AI_MODEL", "gpt-4o-mini")
    if api_key:
        return "openai", {"api_key": api_key, "api_base": api_base, "model": model}

    # 4. Ollama 本地
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            chosen = next(
                (m for m in models if any(k in m for k in ["qwen", "llama", "mistral", "deepseek"])),
                models[0] if models else "llama3"
            )
            return "ollama", {"model": chosen}
    except Exception:
        pass

    # 5. 内置模板 fallback
    return "template", {}


# ════════════════════════════════════════════════════════════
# 提示词构建
# ════════════════════════════════════════════════════════════

def _load_operating_guidelines(user_id: int = None) -> str:
    """加载用户的运营规范，如果未设置则返回空字符串"""
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            return db.get_operating_guidelines(user_id or 0) or ""
    except Exception:
        return ""


def _check_history_duplicates(user_id: int = None, topic_title: str = "", topic_content: str = "") -> List[Dict]:
    """
    检查历史文章是否有重复（用于写稿前去重）。
    两步策略：
    1. bigram 预筛：快速从历史文章中挑出 Top 10 候选（按标题相似度排序）
    2. LLM 语义判断：对每个候选文章判断是否重复及原因（可读历史内容）

    Returns:
        [{title, file_path, created_at, reason}, ...]
    """
    import re as _re
    from pathlib import Path

    if not topic_title or len(topic_title) < 4:
        return []
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            articles = db.get_articles_for_dedup(user_id or 0, limit=100)

        # ── Step 1：bigram 预筛 Top 10 ──────────────────────────────
        def get_ngrams(s, n=2):
            s = _re.sub(r'\s+', '', s)
            return set(s[i:i+n] for i in range(len(s) - n + 1))

        topic_ngrams = get_ngrams(topic_title)
        scored = []
        for article in articles:
            title = article.get("title", "")
            if len(title) < 4:
                continue
            title_ngrams = get_ngrams(title)
            if topic_ngrams and title_ngrams:
                overlap = len(topic_ngrams & title_ngrams)
                ratio = overlap / min(len(topic_ngrams), len(title_ngrams))
                if ratio >= 0.15:  # 宽阈值，仅为初筛
                    scored.append((ratio, article))

        if not scored:
            return []

        # 取 Top 10 候选，按相似度降序
        candidates = [a for _, a in sorted(scored, key=lambda x: -x[0])[:10]]

        # ── Step 2：LLM 语义去重 ──────────────────────────────────
        backend, cfg = _detect_llm_backend(user_id)
        if backend not in ("openai", "ollama"):
            # 无可用 LLM 时降级为 bigram 结果
            return [
                {"title": a.get("title"), "file_path": a.get("file_path"),
                 "created_at": a.get("created_at"), "reason": f"标题相似度 {r:.0%}"}
                for r, a in sorted(scored, key=lambda x: -x[0])[:5]
            ]

        # 拼接候选文章信息（只取前5避免 token 爆炸）
        hist_parts = []
        for a in candidates[:5]:
            file_path = a.get("file_path", "")
            content_preview = ""
            if file_path and Path(file_path).exists():
                try:
                    with open(file_path, encoding="utf-8") as f:
                        raw = f.read()
                    # 取前 800 字（摘要）
                    content_preview = _re.sub(r'[#*`>\-]\s*', '', raw)[:800]
                except Exception:
                    pass
            title = a.get("title", "")
            created = a.get("created_at", "")
            if content_preview:
                hist_parts.append(f"  标题：「{title}」（{created}）\n  内容摘要：{content_preview}")
            else:
                hist_parts.append(f"  标题：「{title}」（{created}）")

        hist_text = "\n\n".join(hist_parts) if hist_parts else "（历史文章标题列表获取失败）"

        dedup_prompt = f"""你是一位资深内容编辑，擅长判断选题是否与历史文章重复。
判断标准（满足任一即视为重复）：
1. 写了同一款产品（同一型号/款型），且角度或核心信息相同
2. 写了同一个品牌/厂商的同类新闻
3. 标题表达的核心意思高度相似

当前选题：
  标题：{topic_title}
  内容摘要：{(topic_content or '无')[:500]}

历史文章（按相似度排序）：
{hist_text}

请逐一分析每个历史文章与当前选题是否重复。
回复格式（严格遵循，仅返回列表，每行一条）：
[重复] 「历史文章标题」 — 重复原因（一句话具体说明）
[不重复] 「历史文章标题」 — 简要说明判断理由

请只回复上述格式的列表，不要任何其他解释文字。"""

        if backend == "openai":
            response = _call_openai(dedup_prompt, cfg)
        else:
            response = _call_ollama(dedup_prompt, cfg)

        # 解析 LLM 回复，提取 [重复] 条目
        duplicates = []
        seen = set()
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line.startswith("[重复]"):
                continue
            # 格式：[重复] 「标题」 — 原因
            parts = line.split("」", 1)
            if len(parts) < 2:
                continue
            title_part = parts[0].replace("[重复] 「", "").strip()
            reason = parts[1].lstrip(" —").strip()
            if title_part not in seen:
                # 找对应的 article 记录
                for a in candidates:
                    if a.get("title") == title_part:
                        duplicates.append({
                            "title": title_part,
                            "file_path": a.get("file_path"),
                            "created_at": a.get("created_at"),
                            "reason": reason
                        })
                        seen.add(title_part)
                        break

        return duplicates
    except Exception:
        return []


def _load_writing_prompt() -> str:
    """从 config_prompt.json 读取自定义写作提示词（writing_prompt 字段）"""
    config_path = BASE_DIR / "config_prompt.json"
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("writing_prompt", "").strip()
    except Exception:
        return ""


def build_article_prompt(
    topic: Dict,
    style: str = "深度科普",
    word_count: int = 2000,
    extra_instructions: str = "",
    custom_writing_prompt: str = "",
    ending_text: str = "感谢阅读，我们下期见。",
    user_id: int = None,
    skill_prompt: str = "",
) -> str:
    """
    构建写文章的完整提示词。
    优先级：skill_prompt > custom_writing_prompt > config_prompt.json 中的 writing_prompt > 默认高质量提示词

    Args:
        topic:                 选题字典（含 title/summary/detail/source_url）
        style:                 文章风格（深度科普/简洁报道/观点评论 等）
        word_count:            目标字数
        extra_instructions:    额外补充指令（直接追加到提示词末尾）
        custom_writing_prompt: 自定义写作提示词
        ending_text:           文章结尾固定词（如"感谢阅读，我们下期见。"）
        skill_prompt:          写作技能提示词（最高优先级，覆盖其他提示词）

    Returns:
        完整 prompt 字符串
    """
    today   = datetime.now().strftime("%Y年%m月%d日")
    # 动态获取当前时段，用于时间约束提示
    _hour = datetime.now().hour
    if _hour < 12:
        _time_context = f"{today} 上午"
    elif _hour < 18:
        _time_context = f"{today} 下午"
    else:
        _time_context = f"{today} 晚上"
    title   = topic.get("title", "未命名选题")
    summary = topic.get("summary", "")
    detail  = topic.get("detail", summary)
    source  = topic.get("source_url", "")

    # 优先读自定义写作提示词（参数 > 配置文件）
    if not custom_writing_prompt:
        custom_writing_prompt = _load_writing_prompt()

    # 写作技能优先级最高：覆盖自定义提示词
    if skill_prompt:
        custom_writing_prompt = skill_prompt

    # 风格指导（无论是否用自定义 prompt，都需要）
    style_guide_map = {
        "深度科普":  "深入浅出，适合普通读者，带出背景、意义和影响；多用类比，少用术语",
        "简洁报道":  "简明克制，直接陈述事实，不过多分析，语气中立客观",
        "观点评论":  "有鲜明立场，逻辑清晰，适当反问，引发读者思考与共鸣",
        "评测对比":  "以用户视角对比优劣，结论明确，数据说话，避免模糊表达",
    }
    style_guide = style_guide_map.get(style, style)

    # 加载运营规范（作为首要参考）
    guidelines = _load_operating_guidelines(user_id)
    guidelines_section = f"""
## 运营规范（最高优先级）
你必须严格遵循以下规范进行写作：

{guidelines}

**重要：以上运营规范是你写作的最高准则。如果文章内容违反上述任何一条规范（如：过时信息、不实信息、低创作度内容、虚假宣传等），必须立即修正。**
""" if guidelines else ""

    if custom_writing_prompt:
        # 用自定义提示词，拼上选题信息 + 本次风格要求
        prompt = f"""{custom_writing_prompt}
{guidelines_section}
---

## 今日写作素材

今天是 {today}.

**选题标题：** {title}
**核心内容：** {summary}
**详细信息：** {detail}
{"**参考来源：** " + source if source else ""}
**目标字数：** {word_count} 字左右
**本次风格：** {style}——{style_guide}

**结尾固定词：** 文章结尾必须使用以下内容：{ending_text}

**日期约束（必须严格遵守）：** 现在是 {_time_context}。文中所有时间表述必须符合当前实际时间——禁止使用"今天下午""今天晚上""刚刚""几小时前""昨天""前天"等尚未发生、无法验证或相对的时间词。只使用已确定的事实性时间（如"{today}""本周""近期"），不要编造具体时刻。

**价格信息约束（汽车类文章必须严格遵守）：**
- 所有车型售价、预售价、起售价、金融方案等价格信息，**必须**来自易车网(https://www.yiche.com)、懂车帝(https://www.dongchedi.com)、汽车之家(https://www.autohome.com.cn)等权威汽车媒体官网数据
- **严禁**自行编造价格数字（如"24.58万起""15.98万租电方案"等）
- 若选题来源并非上述平台，文章中涉及具体价格时，必须在写作时主动补充说明"价格信息请以官方或易车/懂车帝最新公布为准"，不得自行填写未经核实的价格
- 对于未确认的价格信息，标注为"以官方公布为准"，而不是猜测

{extra_instructions}

## 输出格式

直接输出 Markdown 全文，不要加任何解释或前言，从 `# 文章标题` 开始。全文不设置任何 `##` 小标题，用自然段落和过渡句来推进内容，避免AI常见的分节痕迹。
"""
    else:
        # 默认高质量写作提示词（style_guide 已在上方定义）
        prompt = f"""你是一位专业的内容作者，擅长把资讯写得好读、有深度、有温度。
{guidelines_section}
## 写作任务

今天是 {today}，请根据以下选题，写一篇完整的文章。

**选题标题：** {title}
**核心内容：** {summary}
**详细信息：** {detail}
{"**参考来源：** " + source if source else ""}

## 写作要求

**字数：** {word_count} 字左右（不含标题）

**风格：** {style_guide}

**格式禁忌（必须严格遵守）：**
- 禁止使用表格
- 禁止使用无序列表（- 或 *）或有序列表（1. 2. 3.）
- 用段落和自然过渡表达层次，而不是条目罗列

**写作原则：**
- 语言口语化、有节奏感，像在跟朋友说话，而不是写报告
- 每一段都要有钩子，让读者想继续往下读
- 有逻辑层次：开篇抛出问题或悬念 → 逐步展开 → 给出判断或结论
- 只写有据可查的事实，不编造数据、不杜撰细节
- 适当用加粗 **关键词** 强调重点，但不要滥用
- **文章结尾必须使用固定结尾词**：{ending_text}
- **时间约束（必须严格遵守）：现在是 {_time_context}。文中所有时间表述必须符合当前实际时间——禁止使用"今天下午""今天晚上""刚刚""几小时前"等尚未发生或无法验证的时间词。只使用已确定的事实性时间（如"{today}""本周""近期"），不要编造具体时刻**
- **价格信息约束（汽车类文章必须严格遵守）：所有车型售价、预售价、起售价、金融方案等价格信息，必须来自易车网(https://www.yiche.com)、懂车帝(https://www.dongchedi.com)、汽车之家(https://www.autohome.com.cn)等权威汽车媒体官网数据；严禁自行编造价格数字；若价格信息未经确认，一律标注"以官方公布为准"，不得猜测具体数字**

**结构参考：**
- 用 `# 文章标题` 作为全文标题（仅限一个）
- 用自然段落和过渡句推进内容，全文不设 `##` 小标题，避免AI常见的分节感
- 开篇用一句话或一个场景钩住读者
- 结尾收束观点，必须使用固定结尾词

{extra_instructions}

## 输出格式

直接输出 Markdown 全文，不要加任何解释或前言，从 `# 文章标题` 开始。全文不设置任何 `##` 小标题，用自然段落和过渡句来推进内容，避免AI常见的分节痕迹。
"""
    return prompt


# ════════════════════════════════════════════════════════════
# LLM 调用
# ════════════════════════════════════════════════════════════

def _call_openai(prompt: str, config: dict) -> str:
    """调用 OpenAI-compatible API"""
    url     = f"{config['api_base'].rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type":  "application/json",
    }
    system_msg = (
        "你是一位有十年经验的中文科技内容作者，文章已被许多大号转载。"
        "你写作时不会用AI常见的套话，比如「欢迎来到今天的文章」「总的来说」「综上所述」「希望对你有所帮助」；"
        "你不会用项目符号列表，不会写表格；"
        "你习惯用短句，用具体的数字和案例说话，不堆砌形容词；"
        "你有自己的观点，敢于直接下结论，偶尔会质疑和反问；"
        "你的文章读起来像一个真实的人在说话，而不是一台机器在输出。"
    )
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.85,
        "max_tokens": 4000,
    }
    max_retries = 2
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < max_retries - 1:
                print(f"   [ai] API 请求超时/连接失败（第{attempt+1}次），5秒后重试...")
                import time
                time.sleep(5)
            else:
                raise


def _call_ollama(prompt: str, config: dict) -> str:
    """调用本地 Ollama"""
    system_msg = (
        "你是一位有十年经验的中文科技内容作者，文章已被许多大号转载。"
        "你写作时不会用AI常见的套话，比如「欢迎来到今天的文章」「总的来说」「综上所述」「希望对你有所帮助」；"
        "你不会用项目符号列表，不会写表格；"
        "你习惯用短句，用具体的数字和案例说话，不堆砌形容词；"
        "你有自己的观点，敢于直接下结论，偶尔会质疑和反问；"
        "你的文章读起来像一个真实的人在说话，而不是一台机器在输出。"
    )
    payload = {
        "model": config["model"],
        "system": system_msg,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.85, "num_predict": 4000},
    }
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json=payload, timeout=180
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


def _call_template(topic: Dict, style: str, word_count: int) -> str:
    """
    改进版内置模板 fallback — 当没有可用 LLM 时，用真实选题信息生成结构完整的初稿。
    包含选题的真实标题、摘要、详细信息，可作为有价值的草稿使用。
    """
    today    = datetime.now().strftime("%Y年%m月%d日")
    title    = topic.get("title", "今日精选动态")
    summary  = topic.get("summary", "")
    detail   = topic.get("detail", summary)
    src_url  = topic.get("source_url", "")
    keywords = topic.get("keywords", [])

    # 根据风格选择不同的切入角度
    intro_styles = {
        "简洁报道": f"{today}，{summary or title}。这条资讯值得你花 3 分钟了解。",
        "深度科普": f"如果你关注手机圈，{today}这条消息不该错过。",
        "评测对比": f"买手机最怕踩坑。{today}，我们来聊聊{title}。",
        "观点评论": f'说实话，看到「{title}」这个标题，我的第一反应是：终于来了。',
    }
    intro = intro_styles.get(style, f"{today}，一起看看这件值得关注的事。")

    # 从 detail/summary 里提取有用信息
    content_source = detail if detail and detail != summary else summary
    content_paras  = [p.strip() for p in (content_source or "").split("。") if len(p.strip()) >= 8]

    # 构建正文段落
    body_lines = []
    for i, para in enumerate(content_paras[:4]):
        if not para.endswith("。"):
            para += "。"
        body_lines.append(para)

    body_text = "\n\n".join(body_lines) if body_lines else "（详细内容请补充）"

    # 关键词标签（如果有）
    kw_line = ""
    if keywords:
        kw_line = "\n\n**关键词：** " + "、".join(keywords[:5])

    src_line = f"\n\n> 信息来源：{src_url}" if src_url else ""

    return f"""# {title}

{intro}

## 事件速览

{summary or title}

## 详细内容

{body_text}

## 为什么值得关注

这件事的核心价值在于：

- **行业影响**：{title.split('，')[0] if '，' in title else title}的动向，往往预示着下一个方向
- **用户价值**：直接影响消费者的选购决策和使用体验
- **长期趋势**：折射出整个智能手机行业在{today[:7]}的真实走向{kw_line}

## 小结

{title}——这不只是一条新闻，而是一个值得持续跟踪的信号。

你对这件事怎么看？欢迎在评论区聊聊你的想法 👇{src_line}

---
*⚠️ 提示：当前未配置 AI 写作 API，本文为结构化初稿。在 config.json 中填入 `ai_api_key` 可启用完整 AI 写作（推荐 DeepSeek，费用极低）。*
"""


# ════════════════════════════════════════════════════════════
# 主入口：生成文章
# ════════════════════════════════════════════════════════════

def generate_article(
    topic: Dict,
    style: str = "深度科普",
    word_count: int = 1500,
    extra_instructions: str = "",
    save_to_file: bool = True,
    custom_writing_prompt: str = "",
    ending_text: str = "感谢阅读，我们下期见。",
    user_id: int = None,
    skill_prompt: str = "",
) -> Tuple[str, str]:
    """
    根据选题生成完整文章。

    Args:
        topic:                 选题字典
        style:                 文章风格
        word_count:            目标字数
        extra_instructions:    额外写作指令（直接拼入 prompt）
        save_to_file:          是否保存 .md 文件到 output/articles/
        custom_writing_prompt: 自定义写作提示词（优先级高于配置文件）
        ending_text:           文章结尾固定词
        user_id:              用户 ID（用于选择用户的默认 AI 模型）
        skill_prompt:          写作技能提示词（最高优先级）

    Returns:
        (md_content: str, saved_path: str)
        saved_path 为空字符串时表示未保存
    """
    backend, cfg = _detect_llm_backend(user_id)
    print(f"   🤖 LLM 后端：{backend}" + (f"（{cfg.get('model','')}）" if cfg.get("model") else ""))

    # 构建 prompt
    prompt = build_article_prompt(
        topic=topic,
        style=style,
        word_count=word_count,
        extra_instructions=extra_instructions,
        custom_writing_prompt=custom_writing_prompt,
        ending_text=ending_text,
        user_id=user_id,
        skill_prompt=skill_prompt,
    )

    # 调用 LLM
    try:
        if backend == "openai":
            md_content = _call_openai(prompt, cfg)
        elif backend == "ollama":
            md_content = _call_ollama(prompt, cfg)
        else:
            print("   ⚠️  未检测到可用 LLM，使用内置模板（需人工补充内容）")
            md_content = _call_template(topic, style, word_count)
    except Exception as e:
        print(f"   ⚠️  LLM 调用失败（{e}），使用内置模板")
        md_content = _call_template(topic, style, word_count)

    # 保存文件
    saved_path = ""
    if save_to_file:
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title  = re.sub(r'[^\w\u4e00-\u9fff]+', '_', topic.get("title", "article"))[:30]
        filename    = f"{timestamp}_{safe_title}.md"
        saved_path  = str(OUTPUT_DIR / filename)
        with open(saved_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"   ✅ 文章已保存：{saved_path}")

    return md_content, saved_path


# ════════════════════════════════════════════════════════════
# AI 排版（优化 Markdown 语言风格）
# ════════════════════════════════════════════════════════════

_FORMAT_PROMPT = """请优化以下 Markdown 文章的排版和语言风格。

要求：
1. 保持原有的核心内容和观点不变
2. 优化语言表达，使其更自然流畅，去除AI味儿
3. 改善段落结构，使逻辑更清晰
4. **可以删除原有的 ## 小标题，用自然段落过渡替代；原文没有小标题则不添加，保持纯自然段落结构**
5. 保持 Markdown 格式正确（全文标题用 # ，段落小标题用 ## ，更细分用 ### ）
6. 不要改变原文的主旨和重要信息
7. 不要添加任何额外的客套话或总结语

待优化的文章：

{md_text}

请直接返回优化后的 Markdown 内容，不要有任何解释或说明。"""


def ai_format_article(md_content: str, user_id: int = None) -> str:
    """
    使用 AI 优化文章的 Markdown 排版和语言风格。

    Args:
        md_content: 原始 Markdown 文章
        user_id: 用户 ID

    Returns:
        优化后的 Markdown 文章；失败时返回原文
    """
    backend, cfg = _detect_llm_backend(user_id)

    if backend == "template":
        print("   ⚠️  未检测到 AI 服务，跳过 AI 排版")
        return md_content

    prompt = _FORMAT_PROMPT.format(md_text=md_content)

    try:
        if backend == "openai":
            result = _call_openai(prompt, cfg)
        elif backend == "ollama":
            result = _call_ollama(prompt, cfg)
        else:
            print(f"   ⚠️  不支持的 AI 后端 {backend}，跳过 AI 排版")
            return md_content

        result = result.strip()
        if not result:
            return md_content

        print(f"   ✅ AI 排版完成（{len(md_content)} → {len(result)} 字符）")
        return result
    except Exception as e:
        print(f"   ⚠️  AI 排版失败（{e}），保留原文")
        return md_content


# ════════════════════════════════════════════════════════════
# 快速生成：选题 + 写作一步到位
# ════════════════════════════════════════════════════════════

def quick_write(
    title: str,
    background: str = "",
    style: str = "深度科普",
    word_count: int = 1500,
) -> Tuple[str, str]:
    """
    直接给标题和背景，快速生成文章（不需要先跑 auto_selector）。

    Returns:
        (md_content, saved_path)
    """
    topic = {
        "title":      title,
        "summary":    background,
        "detail":     background,
        "source_url": "",
        "is_hot":     True,
    }
    return generate_article(topic, style=style, word_count=word_count)


# ════════════════════════════════════════════════════════════
# CLI 快速测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_topic = {
        "title":      "中兴确认新一代豆包AI手机Q2发布，不再限量",
        "summary":    "中兴通讯在业绩说明会确认与字节跳动继续合作，新一代豆包AI手机预计2026年Q2中晚期发布，首代3万台秒罄，二代有望取消限量。",
        "detail":     "第一代豆包手机二手溢价明显，市场关注度高。新机将延续中兴负责硬件、字节豆包负责AI系统的合作模式。",
        "source_url": "",
        "is_hot":     True,
    }

    backend, cfg = _detect_llm_backend()
    print(f"检测到 LLM 后端：{backend}")

    print("\n🖊️  开始生成文章...")
    md, path = generate_article(test_topic, style="简洁报道", word_count=800)
    print(f"\n{'='*50}")
    print(md[:500] + "\n..." if len(md) > 500 else md)
    print(f"\n文件：{path}")


# ════════════════════════════════════════════════════════════
# 协作写作：选题生成 / 大纲生成 / 内容生成
# ════════════════════════════════════════════════════════════

# ── 本地 fallback 生成器（template 后端或 LLM 异常时使用）──────────

def _fallback_topics(idea: str, count: int = 5) -> List[Dict]:
    """离线选题候选生成：基于 idea 派生 5 个种子选题，截取 count 个。"""
    seeds = [
        {"title": f"深度解读：{idea}",         "description": f"从行业背景、核心原理到未来趋势，全方位解析{idea}。"},
        {"title": f"实用指南：{idea} 怎么用",   "description": f"面向普通读者的实操指南，讲清{idea}的实际使用场景与注意事项。"},
        {"title": f"观点评论：{idea} 意味着什么", "description": f"从产品、用户与行业三个维度，给出对{idea}的独立判断。"},
        {"title": f"评测对比：{idea} 值得买吗",  "description": f"横向对比同类产品，用事实和数据回答{idea}是否值得入手。"},
        {"title": f"热点追踪：{idea} 最新进展",  "description": f"梳理{idea}近期动态，提炼最值得关注的关键信息。"},
    ]
    # 保证返回 3-5 个
    n = max(3, min(count, 5))
    return seeds[:n]


def _fallback_outline(topic: str) -> Dict:
    """离线大纲生成：返回 4 段式大纲。"""
    return {
        "sections": [
            {"id": "s1", "title": f"开篇：为什么关注{topic}",   "points": ["引出话题背景", "点明核心价值"],              "children": []},
            {"id": "s2", "title": f"核心解读：{topic} 是什么",   "points": ["概念/原理解析", "关键特性"],                  "children": []},
            {"id": "s3", "title": f"实用视角：{topic} 怎么用",   "points": ["使用场景", "注意事项"],                      "children": []},
            {"id": "s4", "title": f"总结与展望",                "points": ["核心结论", "后续展望"],                      "children": []},
        ]
    }


def _fallback_content(outline: Dict, section: str = None) -> Dict:
    """离线内容生成：把目标章节映射为带 status 的内容块。"""
    sections = outline.get("sections", [])
    target = sections
    if section is not None:
        target = [s for s in sections if s.get("id") == section] or sections
    result = []
    for s in target:
        points = s.get("points") or []
        body = "。".join(points) if points else f"关于「{s.get('title', '')}」的详细内容。"
        if not body.endswith("。"):
            body += "。"
        result.append({
            "id": s.get("id", ""),
            "title": s.get("title", ""),
            "content": body,
            "status": "generated",
        })
    return {"sections": result}


# ── 公共入口 ────────────────────────────────────────────────

def generate_topics(idea: str, count: int = 5, user_id: int = None) -> List[Dict]:
    """
    根据 idea 生成 3-5 个选题候选。

    Returns:
        [{title, description}, ...]
    """
    backend, cfg = _detect_llm_backend(user_id)
    if backend == "template":
        return _fallback_topics(idea, count)

    prompt = (
        f"你是一位资深选题策划。请根据以下 idea，生成 {count} 个不同的选题候选。\n\n"
        f"idea: {idea}\n\n"
        "每个选题需要 title（标题）和 description（一句话描述）。"
        "返回 JSON 数组，例如 [{\"title\": \"...\", \"description\": \"...\"}]。"
        "不要返回除 JSON 外的任何文字。"
    )
    try:
        if backend == "openai":
            raw = _call_openai(prompt, cfg)
        else:
            raw = _call_ollama(prompt, cfg)
        data = json.loads(raw)
        if not isinstance(data, list) or not data or not isinstance(data[0], dict) or "title" not in data[0]:
            return _fallback_topics(idea, count)
        # 保证每个元素都有 description
        for item in data:
            item.setdefault("description", "")
        return data
    except Exception:
        return _fallback_topics(idea, count)


def generate_outline(topic: str, context: str = None, user_id: int = None) -> Dict:
    """
    根据选题 topic 生成文章大纲。

    Returns:
        {sections: [{id, title, points, children}]}
    """
    backend, cfg = _detect_llm_backend(user_id)
    if backend == "template":
        return _fallback_outline(topic)

    ctx = f"\n\n补充背景：{context}" if context else ""
    prompt = (
        f"你是一位擅长结构化的编辑。请为以下选题设计文章大纲。\n\n"
        f"选题：{topic}{ctx}\n\n"
        "每个章节需要 id（如 s1）、title（标题）、points（要点列表）、children（子章节，可空）。"
        "返回 JSON，例如 {\"sections\": [{\"id\": \"s1\", \"title\": \"...\", \"points\": [...], \"children\": []}]}。"
        "不要返回除 JSON 外的任何文字。"
    )
    try:
        if backend == "openai":
            raw = _call_openai(prompt, cfg)
        else:
            raw = _call_ollama(prompt, cfg)
        data = json.loads(raw)
        if not isinstance(data, dict) or "sections" not in data:
            return _fallback_outline(topic)
        # 修复缺失字段，编号 id
        for i, sec in enumerate(data["sections"], start=1):
            sec.setdefault("id", f"s{i}")
            sec.setdefault("title", "")
            sec.setdefault("points", [])
            sec.setdefault("children", [])
        return data
    except Exception:
        return _fallback_outline(topic)


def generate_content(outline: Dict, section: str = None, user_id: int = None) -> Dict:
    """
    根据大纲生成正文内容。

    Args:
        outline: {sections: [{id, title, points, children}]}
        section: 仅生成指定 id 的章节；为 None 时生成全部。

    Returns:
        {sections: [{id, title, content, status}]}
    """
    backend, cfg = _detect_llm_backend(user_id)
    if backend == "template":
        return _fallback_content(outline, section)

    all_sections = outline.get("sections", [])
    targets = all_sections
    if section is not None:
        targets = [s for s in all_sections if s.get("id") == section] or all_sections

    prompt = (
        "你是一位资深作者。请根据以下章节信息，为每个章节撰写正文。\n\n"
        f"待撰写章节：{json.dumps(targets, ensure_ascii=False)}\n\n"
        "返回 JSON，例如 {\"sections\": [{\"id\": \"s1\", \"title\": \"...\", \"content\": \"...\", \"status\": \"generated\"}]}。"
        "不要返回除 JSON 外的任何文字。"
    )
    try:
        if backend == "openai":
            raw = _call_openai(prompt, cfg)
        else:
            raw = _call_ollama(prompt, cfg)
        data = json.loads(raw)
        if not isinstance(data, dict) or "sections" not in data:
            return _fallback_content(outline, section)
        for sec in data["sections"]:
            sec.setdefault("status", "generated")
        return data
    except Exception:
        return _fallback_content(outline, section)
