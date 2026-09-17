"""
modules/title_generator.py
爆款标题生成模块 — 统一提示词，供所有模块引用

被引用模块：
- article_rewriter.py (链接改写)
- ai_assistant.py (AI小助手)
- web_app.py (Web接口)

提示词设计原理：
- 好奇心缺口理论：已知 vs 想知 的缺口产生填补欲望
- 损失厌恶：错过恐惧 > 得到喜悦
- 社会认同：大众选择更具说服力
"""

import re
from typing import Optional

# ════════════════════════════════════════════════════════════
# 爆款标题生成提示词
# ════════════════════════════════════════════════════════════

TITLE_GEN_PROMPT = """# 角色
你是一位资深自媒体爆款标题编辑，擅长洞察读者心理，能够用多种风格创作高点击率的标题，风格多变，绝不套用固定模板。

## 底层原理（创作依据）

### 好奇心缺口理论（Information Gap Theory）
人一旦感知到「已知」和「想知」之间有缺口，就会产生强烈的填补欲望。标题要在「给够信息」和「保留秘密」之间找到平衡点。

### 损失厌恶（Loss Aversion）
人对「错过」的恐惧远大于「得到」的喜悦。「再不看就晚了」比「快来看看」更有效。

### 社会认同（Social Proof）
人倾向于跟随大众选择。「万人抢购」「爆单」比「热销」更有说服力。

## 标题创作维度（每次选择不同维度组合，不重复使用上一次的套路）

- 冲突感：把两个相矛盾的概念放在一起，制造预期违背
- 数字具象：用数字让抽象变具体，不说「省油」，说「百公里4.2L」
- 身份代入：让读者感觉「在说我」，用「你」「你的」拉近距离
- 时效压迫：制造不立刻看就错过感，用「刚刚」「今天」「最后一天」
- 反问留白：用问句制造思考空间，不给出答案，让读者自己想
- 对比反差：用对比放大冲击力，之前 vs 现在、预期 vs 现实

## 爆款标题特征参考

好标题的特点是：
① 强烈吸引力：《解密：顶级CEO们早晨5点的秘密活动》
② 激发好奇心：《为什么他能从一年内破产到亿万富翁》
③ 情感共鸣：《那些年，我们一起追过的女孩教会我的事》
④ 实用性：《5个简单步骤让你的工作效率翻倍》
⑤ 紧迫感：《限时优惠：今天报名享受半价》
⑥ 热点追踪：《2025年科技大会：AI如何改变我们的未来》
⑦ 精准定位：《30岁以上职场女性如何平衡工作与家庭》
⑧ 创意：《如果历史人物也有社交媒体》
⑨ 权威：《哈佛教授解密：如何培养超级记忆力》
⑩ 互动：《你认为自己有多聪明？来测试一下》
⑪ 价值感、数字、痛点法

请结合以上爆款标题特征，为文章生成爆款标题，标题要适合在内容平台发布。

## 标题技巧
- 用数字增强说服力（具体数字比模糊词更有冲击力）
- 用反差制造冲突（「所有人都以为A，其实B」）
- 用提问激发好奇（「为什么…？」「…的背后是什么？」）
- 用痛点戳中读者（直接说中读者的焦虑或需求）
- 标题要有信息量，读者看完标题就知道这篇文章能获得什么

## 风格要求
- **拒绝标题党**：标题内容和正文必须吻合，不欺骗读者
- **拒绝套路化**：每次生成的标题风格应有所差异，避免雷同
- **语言自然**：语言自然流畅，不用尬词
- **长度适中**：中文标题 12-24 字，过短信息不足，过长折行影响阅读

## 禁止事项
- ❌ 直接抄袭任何现有标题的句式结构
- ❌ 不使用过度夸张的感叹号堆叠（！！！）
- ❌ 不制造与正文无关的虚假悬念
- ❌ 不使用低俗或煽动性词汇
- ❌ 不做标题党，标题承诺的内容文章必须兑现
- ❌ 严禁编造文章中未提及的数据、日期或事实
- ❌ 禁止暗指或对比其他品牌车型（如"对标XX""碾压XX""吊打XX""超越XX"等），文章只聚焦本车型本身，避免引起厂商误会或法律风险

## 限制
- 直接返回标题，无需其他信息
- 不可有特殊字符"""


# ════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════

def _detect_llm_backend(user_id: int = None):
    """检测可用的 LLM 后端（复用 ai_writer 的检测逻辑）"""
    from modules.ai_writer import _detect_llm_backend as _detect
    return _detect(user_id)


def _call_llm(prompt: str, user_id: int = None):
    """统一调用 LLM"""
    from modules.ai_writer import _call_openai, _call_ollama

    backend, config = _detect_llm_backend(user_id)

    if backend == "openai":
        return _call_openai(prompt, config)
    elif backend == "ollama":
        return _call_ollama(prompt, config)
    else:
        raise RuntimeError("未配置 AI 模型，无法生成标题")


def _clean_title_result(result: str) -> str:
    """清理标题结果，去除可能的前后缀标记"""
    result = re.sub(r'^[#*\s*标题[：:]*\s*', '', result)
    result = re.sub(r'^["「【]', '', result)
    result = re.sub(r'["」】]+$', '', result)
    result = result.strip()

    # 如果结果包含换行，只取第一行
    if "\n" in result:
        result = result.split("\n")[0].strip()

    # 如果结果太长，截断
    if len(result) > 50:
        result = result[:50]

    return result


# ════════════════════════════════════════════════════════════
# 标题生成函数
# ════════════════════════════════════════════════════════════

def generate_title(article_body: str, user_id: int = None) -> str:
    """
    根据文章内容生成一个爆款标题。

    Args:
        article_body: 文章正文内容（用于生成标题的依据）
        user_id: 用户 ID（用于选择 AI 模型）

    Returns:
        生成的标题字符串
    """
    # 截取前 1500 字作为标题生成依据（避免超长）
    body_for_title = article_body[:1500]

    prompt = f"""{TITLE_GEN_PROMPT}

## 文章内容

{body_for_title}

请直接返回生成的标题：
"""

    print(f"   [标题生成] 正在生成爆款标题...")
    result = _call_llm(prompt, user_id)
    result = result.strip()
    result = _clean_title_result(result)

    print(f"   [标题生成] 标题生成完成：{result}")
    return result


def generate_titles(article_body: str, count: int = 5, user_id: int = None) -> list:
    """
    根据文章内容生成多个爆款标题（风格各异）。

    Args:
        article_body: 文章正文内容
        count: 生成数量，默认5个
        user_id: 用户 ID

    Returns:
        标题列表
    """
    body_for_title = article_body[:1500]

    prompt = f"""{TITLE_GEN_PROMPT}

## 文章内容

{body_for_title}

## 要求
- 请生成 {count} 个标题，风格各异，覆盖不同的爆款特征
- 每个标题一行，用序号 1-{count} 标注，不要额外解释
"""

    print(f"   [标题生成] 正在生成 {count} 个爆款标题...")
    result = _call_llm(prompt, user_id)
    result = result.strip()

    # 解析多行标题
    titles = []
    for line in result.split("\n"):
        line = line.strip()
        # 跳过空行和元信息行
        if not line or line.startswith("以下") or line.startswith("生成"):
            continue
        # 去除序号前缀
        line = re.sub(r'^\d+[.、:：]\s*', '', line)
        line = _clean_title_result(line)
        if line and len(line) >= 4:
            titles.append(line)

    print(f"   [标题生成] 生成完成，获得 {len(titles)} 个标题")
    return titles[:count]


def suggest_title_from_topic(topic: dict, user_id: int = None) -> str:
    """
    根据选题信息生成爆款标题。

    Args:
        topic: 选题字典，含 title/summary/detail
        user_id: 用户 ID

    Returns:
        生成的标题
    """
    title = topic.get("title", "")
    summary = topic.get("summary", "")
    detail = topic.get("detail", "")

    # 组合素材信息
    content = f"标题：{title}\n\n摘要：{summary}\n\n详情：{detail}"
    return generate_title(content, user_id)


# ════════════════════════════════════════════════════════════
# 向后兼容：保持 article_rewriter 中的名称
# ════════════════════════════════════════════════════════════

_TITLE_GEN_PROMPT = TITLE_GEN_PROMPT  # 向后兼容别名
