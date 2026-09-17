"""
keyword_extractor.py
从文章文本中提取关键词

策略（按优先级降序）：
1. jieba TF-IDF（如果已安装）
2. 纯正则统计：基于词频 + 停用词过滤
3. 标题关键词直提（fallback）

输出统一为 List[str]，默认 top-5。
"""

import re
import math
from collections import Counter
from pathlib import Path
from typing import List, Optional

# ────────────────────────────────────────────────────────
# 停用词表（精简版，覆盖常见中文虚词/功能词）
# ────────────────────────────────────────────────────────
_STOPWORDS = set("""
的 了 和 是 就 都 而 及 与 着 或 一个 没有 我们 你们 他们 她们
在 于 到 从 对 中 为 以 上 下 其 可以 这 那 也 但 更 很 不 已
如果 因为 所以 虽然 但是 然而 因此 如此 通过 使用 进行 实现
一种 一些 这些 那些 我 你 他 她 它 自己 这个 那个 什么 怎么
需要 可以 能够 将会 已经 正在 一直 还是 只是 只有 所有 非常
""".split())

# ────────────────────────────────────────────────────────
# 尝试导入 jieba（可选依赖）
# ────────────────────────────────────────────────────────
try:
    import jieba
    import jieba.analyse
    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False


def extract_keywords(
    text: str,
    title: str = "",
    top_n: int = 5,
    min_len: int = 2,
) -> List[str]:
    """
    从正文和标题中提取关键词

    Args:
        text:    文章正文（Markdown 或纯文本均可）
        title:   文章标题（权重更高）
        top_n:   返回关键词数量
        min_len: 词语最短长度（字符数）

    Returns:
        List[str]: 关键词列表，已去重、按重要性排序
    """
    # 清洗文本：去除 Markdown 语法符号
    clean_body  = _clean_markdown(text)
    clean_title = _clean_markdown(title)

    # 合并（标题权重×3）
    combined = (clean_title + "\n") * 3 + clean_body

    if _JIEBA_AVAILABLE:
        keywords = _jieba_extract(combined, top_n=top_n * 2, min_len=min_len)
    else:
        keywords = _regex_extract(combined, top_n=top_n * 2, min_len=min_len)

    # 标题词优先排序：若关键词出现在标题中，提升到前面
    title_words = set(_tokenize_simple(clean_title))
    # 先快照索引，避免 sort 过程中调用 index 产生 ValueError
    kw_index = {w: i for i, w in enumerate(keywords)}
    keywords.sort(key=lambda w: (0 if w in title_words else 1, kw_index.get(w, 999)))

    # 去重（保序）并截取
    seen = set()
    result = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
        if len(result) >= top_n:
            break

    # 如果结果不足，从标题里补充
    if len(result) < top_n and clean_title:
        for w in _tokenize_simple(clean_title):
            if len(w) >= min_len and w not in seen:
                seen.add(w)
                result.append(w)
            if len(result) >= top_n:
                break

    return result


def extract_summary(text: str, max_chars: int = 120) -> str:
    """
    提取文章摘要（取正文前第一段有效文字）

    Args:
        text:      Markdown 或纯文本
        max_chars: 最大字符数

    Returns:
        str: 摘要文本
    """
    clean = _clean_markdown(text)
    # 按段落分割，取第一段非空内容
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", clean) if p.strip()]
    for para in paragraphs:
        # 跳过太短的段落（可能是标题或标签行）
        if len(para) >= 20:
            summary = para[:max_chars]
            if len(para) > max_chars:
                summary += "…"
            return summary
    return clean[:max_chars] if clean else ""


def suggest_digest(
    text: str,
    title: str = "",
    max_chars: int = 54,
) -> str:
    """
    生成文章摘要（digest 字段，≤54字）

    Args:
        text:      文章正文
        title:     标题（辅助生成）
        max_chars: 最大字符数（限制 54 字）

    Returns:
        str: 摘要字符串
    """
    summary = extract_summary(text, max_chars=max_chars * 3)
    # 截取到字符限制
    digest = summary[:max_chars]
    if len(summary) > max_chars:
        digest = digest.rstrip("，。！？…") + "…"
    return digest


# ────────────────────────────────────────────────────────
# 内部方法
# ────────────────────────────────────────────────────────

def _clean_markdown(text: str) -> str:
    """去除 Markdown 语法，提取纯文本"""
    if not text:
        return ""
    # 代码块
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`[^`]+`", " ", text)
    # 标题符号
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    # 加粗/斜体
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # 链接图片
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # 表格分隔符
    text = re.sub(r"\|[-:]+\|[-|: ]*", " ", text)
    text = re.sub(r"\|", " ", text)
    # 引用符
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    # HTML 标签
    text = re.sub(r"<[^>]+>", " ", text)
    # 多余空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _jieba_extract(text: str, top_n: int, min_len: int) -> List[str]:
    """使用 jieba TF-IDF 提取关键词"""
    try:
        raw = jieba.analyse.extract_tags(
            text,
            topK=top_n,
            withWeight=False,
            allowPOS=("n", "vn", "v", "nr", "ns", "nz", "eng"),
        )
        return [w for w in raw if len(w) >= min_len and w not in _STOPWORDS]
    except Exception:
        return _regex_extract(text, top_n=top_n, min_len=min_len)


def _regex_extract(text: str, top_n: int, min_len: int) -> List[str]:
    """基于词频的简单关键词提取（无需外部依赖）"""
    tokens = _tokenize_simple(text)
    tokens = [t for t in tokens if len(t) >= min_len and t not in _STOPWORDS]

    if not tokens:
        return []

    # 词频统计
    freq = Counter(tokens)
    total = sum(freq.values())

    # 简单 TF 评分（词长加权：长词通常更有意义）
    scored = {
        word: (count / total) * math.log(len(word) + 1)
        for word, count in freq.items()
    }

    top = sorted(scored.items(), key=lambda x: -x[1])[:top_n]
    return [w for w, _ in top]


def _tokenize_simple(text: str) -> List[str]:
    """
    简单分词：
    - 提取连续中文字符（2-6字）
    - 提取英文单词（2+ 字符）
    - 提取数字+字母组合
    """
    # 中文词（2~6个汉字连续）
    cn_words = re.findall(r"[\u4e00-\u9fff]{2,6}", text)
    # 英文词（3+ 字符，避免无意义短词）
    en_words = re.findall(r"[A-Za-z]{3,}", text)
    # 数字+字母（如 GPT-4, AI, 2026）
    mixed = re.findall(r"[A-Za-z0-9][-A-Za-z0-9]*[A-Za-z0-9]", text)

    return cn_words + [w.lower() for w in en_words] + mixed


# ────────────────────────────────────────────────────────
# CLI 测试
# ────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_text = """
# 用 AI 重新定义内容创作

2026 年，AI 已经不再是未来式——它是现在进行时。

## 为什么说内容创作迎来了拐点

过去，一篇高质量的文章需要大量的时间投入，包括选题调研、撰写初稿、排版美化、封面制作等。
现在，借助 AI Agent 技术，这些步骤可以压缩到 **5 分钟以内**。

自然语言处理（NLP）技术的突破让机器理解语言的能力达到了人类水平。
大语言模型（LLM）的出现彻底改变了内容生产的方式。

内容平台作为中国最重要的内容载体之一，正在被 AI 工具重塑。
自动化发布、智能排版、AI 封面生成——这些曾经需要专业团队完成的工作，
现在一个人借助正确的工具就能搞定。

关键词提取、Markdown 转 HTML、自动化发布，这是本系统的核心三大功能。
"""

    title = "用 AI 重新定义内容创作"

    print("=" * 50)
    print("🔍 关键词提取测试")
    print(f"   jieba 可用：{'✅' if _JIEBA_AVAILABLE else '❌ (使用内置词频算法)'}")
    print("=" * 50)

    keywords = extract_keywords(sample_text, title=title, top_n=6)
    print(f"\n📌 提取关键词（top-6）：")
    for i, kw in enumerate(keywords, 1):
        print(f"   {i}. {kw}")

    summary = extract_summary(sample_text)
    print(f"\n📄 文章摘要：\n   {summary}")

    digest = suggest_digest(sample_text, title=title)
    print(f"\n💬 摘要（digest）：\n   {digest}")
    print(f"   字符数：{len(digest)} / 54")
