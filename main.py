"""
main.py
AI 辅助协作写作平台 — 主流程入口

用法：
  python main.py article.md                    # 发布已有 Markdown 文章
  python main.py article.md --theme dark       # 指定封面主题
  python main.py article.md --ai-cover         # 使用 AI 生成封面
  python main.py article.md --preview-only     # 仅预览，不上传
  python main.py --test                        # 运行本地功能测试

  # ── 全自动模式 ──────────────────────────────────────────
  python main.py --auto                        # 用 config.json 中的提示词自动选题→写作→保存本地
  python main.py --auto --style 简洁报道       # 指定文章风格
  python main.py --auto --words 2000           # 指定字数
  python main.py --auto --topic-index 3        # 用第 3 条选题写文章（不自动挑选）
  python main.py --set-prompt                  # 交互式设置选题提示词

流程（全自动模式）：
  自定义提示词
    → 联网搜索选题（auto_selector）
    → AI 生成文章（ai_writer）
    → 关键词提取（keyword_extractor）
    → 保存本地 Markdown 预览
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# ── 项目根目录 ───────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ── 加入模块搜索路径 ─────────────────────────────────────
sys.path.insert(0, str(BASE_DIR))

from modules.keyword_extractor import extract_keywords, suggest_digest, extract_summary

# ── 选题提示词存储路径 ───────────────────────────────────
PROMPT_CONFIG_FILE = BASE_DIR / "config_prompt.json"


# ════════════════════════════════════════════════════════════
# 选题提示词管理
# ════════════════════════════════════════════════════════════

DEFAULT_PROMPT_CONFIG = {
    "topic_prompt": (
        "请整理【当天手机领域最值得关注的 10 条动态】，"
        "重点覆盖以下方向：新机，用机，选机，AI 智能化等热度较高的选题。\n"
        "筛选标准：优先选择具备\"新增信息量\"的动态。\n"
        "优先包含「刚发生/24 小时内」的动态。"
    ),
    "search_queries": [],  # 保留字段用于向后兼容，AI 模式下不使用
    "article_style": "观点评论",
    "word_count": 1500,
    "theme": "blue",
    "extra_instructions": "",
    "_updated": "",
}


def load_prompt_config() -> Dict:
    """加载选题提示词配置（不存在则创建默认值）"""
    if PROMPT_CONFIG_FILE.exists():
        with open(PROMPT_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 合并默认值（保持向后兼容）
        for k, v in DEFAULT_PROMPT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    else:
        save_prompt_config(DEFAULT_PROMPT_CONFIG)
        return DEFAULT_PROMPT_CONFIG.copy()


def save_prompt_config(cfg: Dict):
    """保存提示词配置到 config_prompt.json"""
    cfg["_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(PROMPT_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def interactive_set_prompt():
    """交互式设置选题提示词（终端 stdin）"""
    cfg = load_prompt_config()

    print("\n" + "═" * 60)
    print("📝 设置自动选题提示词")
    print("═" * 60)
    print("\n💡 说明：系统会使用 AI 大模型根据你的提示词直接生成选题，无需手动设置搜索关键词。")
    print("   当 AI 不可用时，会自动降级到传统爬虫 + 搜索方式。\n")
    
    print("\n【当前提示词】（直接回车保留原值）：")
    print(cfg["topic_prompt"])
    print()

    new_prompt = input("新提示词（多行请先写好后粘贴，单行确认）：\n> ").strip()
    if new_prompt:
        cfg["topic_prompt"] = new_prompt

    # 不再主动询问搜索关键词，仅展示
    print(f"\n【搜索关键词】（当前：{cfg.get('search_queries', [])}）")
    print("💡 提示：AI 模式下不需要搜索关键词，如需使用传统模式可手动修改 config_prompt.json")

    print(f"\n【文章风格】（当前：{cfg['article_style']}）")
    print("可选：深度科普 / 简洁报道 / 评测对比 / 观点评论")
    style = input("> ").strip()
    if style:
        cfg["article_style"] = style

    print(f"\n【目标字数】（当前：{cfg['word_count']}）")
    words = input("> ").strip()
    if words.isdigit():
        cfg["word_count"] = int(words)

    print(f"\n【封面主题】（当前：{cfg['theme']}）")
    print("可选：green / dark / blue / warm")
    theme = input("> ").strip()
    if theme in ["green", "dark", "blue", "warm"]:
        cfg["theme"] = theme

    save_prompt_config(cfg)
    print(f"\n✅ 提示词已保存到 {PROMPT_CONFIG_FILE.name}")
    print("下次运行 `python main.py --auto` 将使用新设置。")


# ════════════════════════════════════════════════════════════
# 全自动流水线：选题 → 写作 → 发布
# ════════════════════════════════════════════════════════════

def run_auto_pipeline(
    config: Dict,
    prompt_cfg: Dict,
    draft_only: bool = True,
    topic_index: Optional[int] = None,
    style_override: str = "",
    domain_override: str = "",
    words_override: int = 0,
    theme_override: str = "",
    cache_hours: float = 6.0,
    custom_writing_prompt: str = "",
    account_db_id: int = 0,
    user_id: int = 1,
    skill_prompt: str = "",
) -> Dict[str, Any]:
    """
    全自动流水线：联网选题 → AI 写作 → 转 HTML

    Args:
        config:         主配置
        prompt_cfg:     选题提示词配置
        draft_only:     True = 仅存草稿，不提交发布
        topic_index:    手动指定第几条选题（None = 自动根据评分生成多篇文章）
        style_override: 覆盖文章风格
        words_override: 覆盖字数（0 = 使用 prompt_cfg 中的值）
        theme_override: 覆盖封面主题
        cache_hours:    选题缓存时长（0 = 不缓存，强制重新搜索）
        custom_writing_prompt: 自定义写作提示词
        account_db_id:  账号数据库 ID（用于保存文章记录）
        user_id:        当前用户 ID（默认 1 = admin）
        skill_prompt:   写作技能提示词（最高优先级）

    Returns:
        dict: 完整流程结果
    """
    from modules.auto_selector import generate_topics, pick_best_topic, format_topics_markdown
    from modules.ai_writer     import generate_article

    style = style_override or prompt_cfg.get("article_style", "观点评论")
    words = words_override  or prompt_cfg.get("word_count", 1500)
    theme = theme_override  or prompt_cfg.get("theme", "blue")
    # 从账号配置读取 author，而不是从 AI 配置
    effective_user_id = user_id if account_db_id > 0 else None
    account_config = get_account_config(account_db_id=account_db_id, user_id=effective_user_id)
    author = account_config.get("author", "")
    ending_text = account_config.get("ending_text", "感谢阅读，我们下期见。")

    # ── Step 1：联网选题 ──────────────────────────────────
    # 注意：选题优先按领域爬取对应网站，再由搜索引擎补充
    domain = domain_override or ""
    print(f"\n🔍 Step 1/5：联网自动选题...（领域：{domain or '未指定'}）")
    topics = generate_topics(
        prompt=prompt_cfg["topic_prompt"],
        domain=domain,
        search_queries=prompt_cfg.get("search_queries"),
        max_topics=10,
        cache_hours=cache_hours,
        user_id=user_id,
    )

    if not topics:
        return {"success": False, "msg": "未能获取任何选题，请检查网络连接"}

    print(f"   获取到 {len(topics)} 条选题")

    # 展示选题列表
    for t in topics[:5]:
        hot = "🔥" if t.get("is_hot") else "  "
        ai_score = t.get("ai_score", 0)
        score_str = f"({ai_score:.1f}分)" if ai_score > 0 else ""
        print(f"   {hot} {t['rank']}. {t['title']} {score_str}")
    if len(topics) > 5:
        print(f"   ... 共 {len(topics)} 条")

    # ── Step 2：根据评分选择要写的文章数量 ─────────────
    # 手动指定选题时，只写一篇
    if topic_index is not None:
        idx = max(0, min(topic_index - 1, len(topics) - 1))
        chosen_topics = [topics[idx]]
        print(f"\n📌 手动选定第 {idx + 1} 条：{chosen_topics[0]['title']}")
    else:
        # 自动模式：根据 AI 评分决定生成1-3篇高质量文章
        # 评分 >= 8.0：生成 3 篇
        # 评分 >= 7.0：生成 2 篇
        # 评分 >= 6.0：生成 1 篇
        # 评分 < 6.0：只选 1 篇（fallback）
        scored_topics = [t for t in topics if t.get("ai_score", 0) >= 1.0]

        if not scored_topics:
            # 没有评分，降级到原有的逻辑（只选最热的1篇）
            chosen = pick_best_topic(topics)
            chosen_topics = [chosen]
            print(f"\n🏆 无 AI 评分，选择热点选题：{chosen['title']}")
        else:
            # 根据评分决定生成文章数量
            top_score = scored_topics[0].get("ai_score", 0)
            if top_score >= 8.0:
                num_articles = min(3, len(scored_topics))
                print(f"\n🏆 最高评分 {top_score:.1f} 分 >= 8.0，将生成 {num_articles} 篇高质量文章")
            elif top_score >= 7.0:
                num_articles = min(2, len(scored_topics))
                print(f"\n🏆 最高评分 {top_score:.1f} 分 >= 7.0，将生成 {num_articles} 篇高质量文章")
            else:
                num_articles = 1
                print(f"\n🏆 最高评分 {top_score:.1f} 分 >= 6.0，将生成 1 篇文章")

            chosen_topics = scored_topics[:num_articles]

    # ── Step 3：批量 AI 写文章 ───────────────────────────
    results = []
    all_articles = []

    for idx, chosen in enumerate(chosen_topics, 1):
        print(f"\n🖊️  正在生成第 {idx}/{len(chosen_topics)} 篇文章：{chosen['title']}")
        print(f"   风格：{style}，字数：{words}，评分：{chosen.get('ai_score', 0):.1f}")

        extra = prompt_cfg.get("extra_instructions", "")
        md_content, md_path = generate_article(
            topic=chosen,
            style=style,
            word_count=words,
            extra_instructions=extra,
            save_to_file=True,
            custom_writing_prompt=custom_writing_prompt,
            ending_text=ending_text,
            user_id=user_id,
            skill_prompt=skill_prompt,
        )

        if not md_content.strip():
            print(f"   ⚠️  第 {idx} 篇文章生成失败，跳过")
            continue

        # ── Step 3.5：爆款标题替换 ─────────────────────
        try:
            from modules.article_rewriter import generate_title
            # 提取文章正文（去掉 # 标题行）用于标题生成
            body_text = re.sub(r'^#\s+.+\n*', '', md_content, count=1)
            viral_title = generate_title(body_text, user_id=user_id)
            if viral_title and viral_title.strip():
                # 替换 md_content 中的 # 标题
                import re as _re
                new_md = _re.sub(r'^#\s+.+\n*', f'# {viral_title.strip()}\n\n', md_content, count=1)
                # 同时更新保存的文件
                if md_path:
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(new_md)
                md_content = new_md
                print(f"   🔥 爆款标题：{viral_title.strip()}")
            else:
                print(f"   ⚠️  爆款标题生成失败，保留原标题")
        except Exception as e:
            print(f"   ⚠️  爆款标题生成异常（{e}），保留原标题")

        # ── Step 3.8：AI 排版优化 ──────────────────────
        try:
            from modules.ai_writer import ai_format_article
            formatted_md = ai_format_article(md_content, user_id=user_id)
            if formatted_md != md_content:
                md_content = formatted_md
                # 同步更新保存的文件
                if md_path:
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(md_content)
        except Exception as e:
            print(f"   ⚠️  AI 排版异常（{e}），保留原文")

        print(f"   ✅ 文章长度：{len(md_content)} 字符")

        # ── Step 4：走标准发布流水线 ────────────────────
        print(f"⚙️  转换 HTML → 生成封面 → 推送草稿...")
        result = run_publish_pipeline(
            md_path=md_path,
            config=config,
            draft_only=draft_only,
            preview_only=False,
            theme=theme,
            use_ai_cover=False,
            author_override=author,
            account_db_id=account_db_id,
            user_id=user_id,
        )

        result["selected_topic"] = chosen
        result["article_index"] = idx
        result["total_articles"] = len(chosen_topics)
        result["saved_path"] = str(md_path)

        results.append(result)
        all_articles.append({
            "topic": chosen,
            "md_path": md_path,
            "result": result
        })

    # ── 返回结果 ──────────────────────────────────────────
    # 如果只生成了1篇，保持向后兼容
    if len(results) == 1:
        final_result = results[0]
        final_result["topics_count"] = len(topics)
        final_result["mode"] = "auto_draft" if draft_only else "auto_publish"
        return final_result
    else:
        # 多篇文章，返回汇总结果
        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]
        return {
            "success": len(successful) > 0,
            "msg": f"成功生成 {len(successful)}/{len(results)} 篇文章",
            "total_articles": len(results),
            "successful_articles": len(successful),
            "failed_articles": len(failed),
            "articles": all_articles,
            "topics_count": len(topics),
            "mode": "auto_draft" if draft_only else "auto_publish",
        }




def load_config() -> Dict:
    """从 config.json 加载 AI 配置"""
    config_path = BASE_DIR / "config.json"
    cfg = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    return cfg


def get_account_config(account_db_id: int = 0, user_id: Optional[int] = None) -> Dict:
    """
    从数据库获取指定账号的完整配置（含 author/ending_text 等）

    Args:
        account_db_id: 账号数据库 ID，0 表示使用默认账号
        user_id: 用户 ID，None 表示使用 admin 用户

    Returns:
        账号配置字典
    """
    from modules.user_db import UserDB

    # 如果没有指定 user_id，获取 admin 用户
    if user_id is None:
        with UserDB() as db:
            cur = db.conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
            admin = cur.fetchone()
            if admin:
                user_id = admin[0]

    # 从数据库获取账号配置
    with UserDB() as db:
        if account_db_id > 0:
            account = db.get_account_by_id(account_db_id)
        else:
            account = db.get_user_default_account(user_id) if user_id else None

        if account:
            return dict(account)

    return {}


# ════════════════════════════════════════════════════════════
# 核心发布流程
# ════════════════════════════════════════════════════════════

def run_publish_pipeline(
    md_path: str,
    config: Dict,
    draft_only: bool = False,
    preview_only: bool = False,
    theme: str = "blue",
    template: str = "",
    use_ai_cover: bool = False,
    title_override: str = "",
    author_override: str = "",
    account_db_id: int = 0,
    user_id: int = 1,
) -> Dict[str, Any]:
    """
    本地生成流水线

    Args:
        md_path:        Markdown 文件路径
        config:         AI 配置字典（从 config.json 加载）
        draft_only:     True = 仅存草稿，不提交发布
        preview_only:   True = 仅本地预览
        theme:          封面主题（green/dark/blue/warm）
        template:       排版模板（classic/magazine/tech/minimal/notebook）
        use_ai_cover:   是否尝试调用 AI 生成封面
        title_override: 覆盖标题（不填则从文件名推断）
        author_override:覆盖作者名
        account_db_id:  账号数据库 ID（用于保存文章记录，0 表示不保存）
        user_id:        当前用户 ID（默认 1 = admin）

    Returns:
        dict: 流程结果
    """
    # ── 从数据库加载账号配置（author/ending_text 等）
    # 注意：main.py 中直接调用时 user_id 传 None，让函数自动查找 admin 用户
    effective_user_id = user_id if account_db_id > 0 else None
    account_config = get_account_config(account_db_id=account_db_id, user_id=effective_user_id)
    author = author_override or account_config.get("author", "")
    ending_text = account_config.get("ending_text", "感谢阅读，我们下期见。")

    # 如果调用时传入 account_db_id=0，但数据库里有默认账号，则使用数据库返回的真实 ID
    # 这样后续数据库写入（if account_db_id > 0）才能正常执行
    if account_db_id == 0 and account_config.get("id"):
        account_db_id = account_config["id"]

    md_file = Path(md_path)
    if not md_file.exists():
        return {"success": False, "msg": f"文件不存在：{md_path}"}

    # ────────────────────────────────────────────
    # Step 1：读取 Markdown
    # ────────────────────────────────────────────
    with open(md_file, "r", encoding="utf-8") as f:
        md_text = f.read()

    # 提取标题（优先第一个 # 标题）
    title = title_override or _extract_title_from_md(md_text) or md_file.stem
    print(f"\n📄 文章：{title}")

    # ────────────────────────────────────────────
    # Step 2：关键词提取 + 摘要
    # ────────────────────────────────────────────
    print("🔍 提取关键词...")
    keywords = extract_keywords(md_text, title=title, top_n=5)
    digest   = suggest_digest(md_text, title=title)
    summary  = extract_summary(md_text)

    print(f"   关键词：{' / '.join(keywords)}")
    print(f"   摘要：{digest[:40]}...")

    # ────────────────────────────────────────────
    # Step 3：保存本地预览（纯 Markdown 输出）
    # ────────────────────────────────────────────
    print("📝 保存本地预览...")
    preview_dir = BASE_DIR / "output" / "drafts"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_filename = f"{md_file.stem}_preview.md"
    preview_path = preview_dir / preview_filename
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"   ✅ 预览文件：{preview_path}")

    return {
        "success": True,
        "mode": "local_only",
        "title": title,
        "keywords": keywords,
        "digest": digest,
        "preview_path": str(preview_path),
        "msg": "本地文件已生成",
    }


# ════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════

def _extract_title_from_md(md_text: str) -> str:
    """从 Markdown 提取第一个一级标题"""
    import re
    match = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _print_result(result: Dict):
    """美化打印流程结果"""
    print("\n" + "═" * 55)
    if result.get("success"):
        mode = result.get("mode", "publish")
        if mode == "preview":
            print("✅ 预览完成")
        elif mode == "local_only":
            print("✅ 本地生成完成（未发布）")
        else:
            print("🎉 发布成功！")

        if result.get("preview_path"):
            print(f"   📄 预览文件：{result['preview_path']}")
        if result.get("cover_path"):
            print(f"   🖼️  封面图：{result['cover_path']}")
        if result.get("media_id"):
            print(f"   📦 草稿 ID：{result['media_id']}")
        if result.get("publish_id"):
            print(f"   🚀 发布任务：{result['publish_id']}")
        if result.get("keywords"):
            print(f"   🏷️  关键词：{' / '.join(result['keywords'])}")
        if result.get("msg"):
            print(f"   💬 {result['msg']}")
    else:
        print(f"❌ 失败：{result.get('msg', '未知错误')}")
    print("═" * 55)


# ════════════════════════════════════════════════════════════
# 本地功能测试
# ════════════════════════════════════════════════════════════

def run_local_test():
    """不需要平台账号，纯本地测试通用模块"""
    print("\n" + "=" * 55)
    print("🧪 本地功能测试（不需要平台配置）")
    print("=" * 55)

    sample_md = """# 用 AI 重新定义内容创作

2026 年，AI 已经不再是未来式——它是现在进行时。

## 为什么说内容创作迎来了拐点

过去，一篇高质量的文章需要大量时间投入。
现在，借助 **AI Agent** 技术，可以压缩到 **5 分钟以内**。

## 核心技术路径

### 第一步：智能选题

```python
# 调用 AI 生成选题
article = ai_writer.generate(topic="AI 趋势", style="深度")
```

### 第二步：自动排版

> 所有样式必须内联，以便跨平台使用。

| 模块 | 工具 | 耗时 |
|------|------|------|
| MD解析 | mistune | <50ms |
| CSS内联 | premailer | <100ms |

## 总结

**效率提升，让创作者专注于思考和判断。**
"""

    print("\n[1/2] 测试关键词提取...")
    from modules.keyword_extractor import extract_keywords, suggest_digest
    kws = extract_keywords(sample_md, title="用 AI 重新定义内容创作", top_n=5)
    digest = suggest_digest(sample_md)
    print(f"   关键词：{kws}")
    print(f"   摘要：{digest}")

    print("\n[2/2] 测试本地 Markdown 预览输出...")
    preview_dir = BASE_DIR / "output" / "drafts"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_path = preview_dir / "main_test_preview.md"
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(sample_md)
    print(f"   预览文件：{preview_path}")

    print("\n✅ 所有本地测试通过！")
    print(f"   预览目录：{BASE_DIR / 'output' / 'drafts'}")


# ════════════════════════════════════════════════════════════
# CLI 入口
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="AI 辅助协作写作平台",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
示例：
  python main.py article.md                  # 发布已有文章
  python main.py article.md --preview-only   # 仅本地预览
  python main.py article.md --theme dark     # 深色封面
  python main.py --auto                      # 全自动：选题→写作→保存本地
  python main.py --auto --style 简洁报道     # 指定文章风格
  python main.py --auto --words 2000         # 指定字数
  python main.py --auto --topic-index 3      # 用第3条选题
  python main.py --set-prompt                # 交互式修改选题提示词
  python main.py --test                      # 本地测试
        """,
    )

    parser.add_argument("md_file",         nargs="?",  help="Markdown 文件路径")
    parser.add_argument("--preview-only",  action="store_true", help="仅本地预览")
    parser.add_argument("--ai-cover",      action="store_true", help="使用 AI 生成封面")
    parser.add_argument("--theme",         default="",
                        choices=["", "green", "dark", "blue", "warm"],
                        help="封面主题（默认 green）")
    parser.add_argument("--title",         default="", help="覆盖标题")
    parser.add_argument("--author",        default="", help="覆盖作者名")
    parser.add_argument("--test",          action="store_true", help="运行本地功能测试")
    parser.add_argument("--config",        default="", help="指定 config.json 路径")

    # ── 全自动模式 ────────────────────────────────────────
    parser.add_argument("--auto",          action="store_true",
                        help="全自动模式：选题→AI写作→推草稿")
    parser.add_argument("--set-prompt",    action="store_true",
                        help="交互式设置选题提示词")
    parser.add_argument("--show-prompt",   action="store_true",
                        help="显示当前选题提示词配置")
    parser.add_argument("--style",         default="",
                        help="文章风格（深度科普/简洁报道/评测对比/观点评论）")
    parser.add_argument("--words",         type=int, default=0,
                        help="文章字数（默认 1500）")
    parser.add_argument("--topic-index",   type=int, default=None,
                        help="手动指定使用第几条选题（1-10）")
    parser.add_argument("--no-cache",      action="store_true",
                        help="不使用选题缓存，强制重新搜索")

    args = parser.parse_args()

    # ── 本地测试模式 ──────────────────────────────────────
    if args.test:
        run_local_test()
        return

    # ── 设置提示词 ────────────────────────────────────────
    if args.set_prompt:
        interactive_set_prompt()
        return

    # ── 显示当前提示词 ────────────────────────────────────
    if args.show_prompt:
        cfg = load_prompt_config()
        print("\n" + "═" * 60)
        print("📋 当前选题提示词配置")
        print("═" * 60)
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return

    # ── 加载主配置 ────────────────────────────────────────
    if args.config:
        with open(args.config, "r") as f:
            config = json.load(f)
    else:
        config = load_config()

    # ── 全自动模式 ────────────────────────────────────────
    if args.auto:
        prompt_cfg = load_prompt_config()
        # theme 优先级：命令行 > prompt_cfg
        theme = args.theme or prompt_cfg.get("theme", "blue")
        result = run_auto_pipeline(
            config=config,
            prompt_cfg=prompt_cfg,
            topic_index=args.topic_index,
            style_override=args.style,
            words_override=args.words,
            theme_override=theme,
            cache_hours=0 if args.no_cache else 6.0,
        )
        _print_result(result)
        return

    # ── 主流程（手动指定 md 文件） ────────────────────────
    if not args.md_file:
        parser.print_help()
        return

    theme = args.theme or "blue"
    result = run_publish_pipeline(
        md_path=args.md_file,
        config=config,
        preview_only=args.preview_only,
        theme=theme,
        use_ai_cover=args.ai_cover,
        title_override=args.title,
        author_override=args.author,
    )

    _print_result(result)


if __name__ == "__main__":
    main()
