"""
auto_selector.py
自动选题模块 — 联网搜索 + 自定义提示词 → 结构化选题列表

选题来源优先级：
  1. 按领域爬取对应的数据源（RSS/HTML）
  2. Bing Search API（有 BING_SEARCH_KEY 环境变量时使用）
  3. DuckDuckGo HTML 接口（随机延迟防限流）
  4. 直接爬取科技媒体（IT之家 / 36氪 / 快科技）RSS/文章列表（作为兜底）
     — 最稳定，无需 Key，无频率限制

依赖：requests, lxml（已在 requirements.txt）
"""

import os
import json
import re
import time
import random
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import unquote

# ── 缓存目录 ────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BING_SEARCH_URL = "https://api.bing.microsoft.com/v7.0/search"


def _load_operating_guidelines(user_id: int = None) -> str:
    """加载用户的运营规范，如果未设置则返回空字符串"""
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            return db.get_operating_guidelines(user_id or 0) or ""
    except Exception:
        return ""

# 随机 User-Agent 池
_UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# 领域配置
_DOMAINS_CONFIG = None


def _load_domains_config() -> dict:
    """加载领域配置文件"""
    global _DOMAINS_CONFIG
    if _DOMAINS_CONFIG is not None:
        return _DOMAINS_CONFIG

    config_path = CACHE_DIR.parent / "domains_config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _DOMAINS_CONFIG = json.load(f)
    except Exception as e:
        print(f"   ⚠️  加载领域配置失败：{e}")
        _DOMAINS_CONFIG = {"domains": {}}
    return _DOMAINS_CONFIG


def _get_domain_config(domain: str) -> dict:
    """获取指定领域的配置"""
    config = _load_domains_config()
    domains = config.get("domains", {})
    # 如果指定领域不存在，返回"其他"领域配置
    return domains.get(domain, domains.get("其他", {}))


def _rand_headers() -> dict:
    return {
        "User-Agent": random.choice(_UA_POOL),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


# ════════════════════════════════════════════════════════════
# 科技媒体直接爬虫（最稳定，无需搜索引擎）
# ════════════════════════════════════════════════════════════

def _fetch_ithome_mobile(max_results: int = 15) -> List[Dict]:
    """爬取 IT之家手机频道最新文章"""
    results = []
    try:
        resp = requests.get(
            "https://www.ithome.com/mobile/",
            headers=_rand_headers(),
            timeout=10,
        )
        resp.encoding = "utf-8"
        html = resp.text

        # 提取文章标题和链接
        items = re.findall(
            r'<a\s+[^>]*href="(https://www\.ithome\.com/0/[^"]+)"[^>]*>\s*<h2[^>]*>([^<]{5,80})</h2>',
            html,
        )
        if not items:
            # 备用正则
            items = re.findall(
                r'href="(https://www\.ithome\.com/0/\d+/\d+\.htm)"[^>]*title="([^"]{5,80})"',
                html,
            )

        for url, title in items[:max_results]:
            title = title.strip()
            if title and len(title) >= 4:
                results.append({
                    "title":   title,
                    "url":     url,
                    "snippet": f"IT之家报道：{title}",
                })
    except Exception as e:
        print(f"   [ithome] 爬取失败：{e}")
    return results


def _parse_rss_pubdate(item_xml: str) -> Optional[datetime]:
    """
    从 RSS <item> XML 中解析 <pubDate> 字段，返回 datetime 对象。
    支持常见格式：
      - RFC 2822: "Wed, 30 Apr 2026 10:30:00 +0800"
      - ISO 8601: "2026-04-30T10:30:00+08:00"
    解析失败时返回 None。
    """
    from datetime import timedelta
    pub_m = re.search(r'<pubDate>\s*(.*?)\s*</pubDate>', item_xml, re.IGNORECASE)
    if not pub_m:
        return None
    raw = pub_m.group(1).strip()
    # 尝试 RFC 2822
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(raw).replace(tzinfo=None)
    except Exception:
        pass
    # 尝试 ISO 8601（去掉时区后缀）
    try:
        clean = re.sub(r'[+-]\d{2}:\d{2}$', '', raw).strip().replace('T', ' ')
        return datetime.strptime(clean[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return None



    """爬取 36氪 手机/数码相关最新文章（RSS）"""
    from datetime import timedelta
    results = []
    cutoff = datetime.now() - timedelta(days=7)  # 只保留近 7 天
    try:
        resp = requests.get(
            "https://36kr.com/feed",
            headers=_rand_headers(),
            timeout=10,
        )
        resp.encoding = "utf-8"
        text = resp.text

        # RSS item 提取
        items_raw = re.findall(r'<item>(.*?)</item>', text, re.DOTALL)
        for item_xml in items_raw[:30]:
            title_m = (
                re.search(r'<title><!\[CDATA\[(.*?)\]\]>', item_xml)
                or re.search(r'<title>\s*([^<]{4,100})\s*</title>', item_xml)
            )
            link_m  = re.search(r'<link>\s*(https?://[^\s<]+)\s*</link>', item_xml)
            desc_m  = (
                re.search(r'<description><!\[CDATA\[(.*?)\]\]>', item_xml, re.DOTALL)
                or re.search(r'<description>\s*([^<]{4,})\s*</description>', item_xml, re.DOTALL)
            )

            if not title_m:
                title_m = re.search(r'<title>(.*?)</title>', item_xml)

            if title_m:
                # 解析发布时间，过滤 7 天以上旧内容
                pub_dt = _parse_rss_pubdate(item_xml)
                if pub_dt and pub_dt < cutoff:
                    continue  # 跳过旧内容

                title   = title_m.group(1).strip()
                url     = link_m.group(1).strip() if link_m else ""
                raw_desc = desc_m.group(1) if desc_m else ""
                snippet = re.sub(r'<[^>]+>', '', raw_desc).strip()[:150]

                # 在摘要中注入发布日期（便于后续 _filter_recent_results 识别）
                if pub_dt:
                    date_str = pub_dt.strftime("%Y年%m月%d日")
                    snippet = f"[{date_str}] {snippet}" if snippet else date_str

                # 只保留手机/科技相关
                mobile_kws = ["手机", "iPhone", "Android", "华为", "小米", "OPPO",
                              "vivo", "荣耀", "三星", "苹果", "芯片", "AI", "5G",
                              "智能", "数码", "设备", "发布", "新机", "旗舰"]
                if any(kw in title for kw in mobile_kws):
                    results.append({
                        "title":   title[:80],
                        "url":     url,
                        "snippet": snippet or f"36氪报道：{title}",
                    })
                    if len(results) >= max_results:
                        break
    except Exception as e:
        print(f"   [36kr] 爬取失败：{e}")
    return results


def _fetch_ithome_rss(category_url: str, max_results: int = 15) -> List[Dict]:
    """通用 IT之家 RSS 爬取"""
    from datetime import timedelta
    results = []
    cutoff = datetime.now() - timedelta(days=7)  # 只保留近 7 天
    try:
        resp = requests.get(category_url, headers=_rand_headers(), timeout=10)
        resp.encoding = "utf-8"
        text = resp.text

        items_raw = re.findall(r'<item>(.*?)</item>', text, re.DOTALL)
        for item_xml in items_raw[:max_results * 2]:
            # title：兼容 CDATA 和普通文本两种格式
            title_m = (
                re.search(r'<title><!\[CDATA\[(.*?)\]\]>', item_xml)
                or re.search(r'<title>\s*([^<]{4,100})\s*</title>', item_xml)
            )
            link_m  = re.search(r'<link>\s*(https?://[^\s<]+)\s*</link>', item_xml)
            desc_m  = (
                re.search(r'<description><!\[CDATA\[(.*?)\]\]>', item_xml, re.DOTALL)
                or re.search(r'<description>\s*([^<]{4,})\s*</description>', item_xml, re.DOTALL)
            )

            if title_m:
                # 解析发布时间，过滤 7 天以上旧内容
                pub_dt = _parse_rss_pubdate(item_xml)
                if pub_dt and pub_dt < cutoff:
                    continue  # 跳过旧内容

                title    = title_m.group(1).strip()
                url      = link_m.group(1).strip() if link_m else ""
                raw_desc = desc_m.group(1) if desc_m else ""
                snippet  = re.sub(r'<[^>]+>', '', raw_desc).strip()[:200]

                # 在摘要中注入发布日期（便于后续 _filter_recent_results 识别）
                if pub_dt:
                    date_str = pub_dt.strftime("%Y年%m月%d日")
                    snippet = f"[{date_str}] {snippet}" if snippet else date_str

                if title and len(title) >= 4:
                    results.append({
                        "title":   title[:80],
                        "url":     url,
                        "snippet": snippet or title,
                    })
                    if len(results) >= max_results:
                        break
    except Exception as e:
        print(f"   [rss:{category_url[:40]}] 爬取失败：{e}")
    return results


def _load_db_domain_config(domain: str) -> dict:
    """
    从数据库读取领域配置（ref_websites 字段）。
    返回 {"name": ..., "ref_websites": [...], "search_keywords": [...]}
    """
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            # 按领域名称查找
            cur = db.conn.cursor()
            cur.execute("SELECT name, ref_websites FROM domains WHERE name = ?", (domain,))
            row = cur.fetchone()
            if row:
                name, ref_json = row
                ref_sites = []
                if ref_json:
                    try:
                        ref_sites = json.loads(ref_json) if isinstance(ref_json, str) else ref_json
                    except (json.JSONDecodeError, TypeError):
                        pass
                return {"name": name, "ref_websites": ref_sites}
    except Exception as e:
        print(f"   [领域] ⚠️ 读取数据库领域配置失败：{e}")
    return {}


def _fetch_domain_news(domain: str, topic_keywords: List[str], max_results: int = 20) -> List[Dict]:
    """
    根据领域爬取对应的新闻源。
    数据来源优先级：数据库 ref_websites > domains_config.json > 搜索引擎补充
    """
    all_sources = []   # 合并后的数据源列表
    domain_keywords = []

    # 1. 从数据库读取用户配置的领域网站
    db_config = _load_db_domain_config(domain)
    db_sites = db_config.get("ref_websites", [])
    if db_sites:
        print(f"   [领域] 从数据库获取到 {len(db_sites)} 个专属网站")
        for site in db_sites[:5]:
            # 兼容三种格式：
            # 1. 字典 {name, url}（正常格式）
            # 2. 字典但 name/url 之一被污染成 "名称：URL" 格式（解析异常）
            # 3. 原始字符串 "名称：URL"
            if isinstance(site, str):
                # 格式3：字符串直接解析
                parts = re.split(r"\s*[:：]\s*", site, maxsplit=1)
                if len(parts) == 2 and parts[1].startswith("http"):
                    name, url = parts[0], parts[1]
                else:
                    print(f"   [领域]   ⚠️ 跳过无效格式：{repr(site)}")
                    continue
            else:
                name = site.get("name", "未知")
                url = site.get("url", "")
                # 格式2：url 本身被污染成 "名称：URL"，需要二次解析
                if url and not url.startswith("http") and "：" in url:
                    parts = re.split(r"\s*[:：]\s*", url, maxsplit=1)
                    if len(parts) == 2 and parts[1].startswith("http"):
                        name, url = parts[0], parts[1]
                    elif len(parts) == 2 and not parts[1].startswith("http"):
                        # 污染到了 name 字段，url 其实是个描述，name 才包含 URL
                        # 比如 name="汽车之家", url="https://..." 正常情况下
                        # 这里 name 包含冒号说明 name 本身被污染了
                        name = url  # 互换
                        url = parts[0]

            if not url or not url.startswith("http"):
                print(f"   [领域]   ⚠️ 跳过（URL为空）：名称={name}")
                continue
            if not url.startswith("http"):
                print(f"   [领域]   ⚠️ 跳过（非HTTP URL）：名称={name}，URL={repr(url)}")
                continue
            print(f"   [领域]   → 爬取 {name}：{url[:60]}")
            try:
                resp = requests.get(url, headers=_rand_headers(), timeout=10)
                resp.encoding = resp.apparent_encoding or "utf-8"
                html = resp.text
                items = re.findall(
                    r'<a\s+[^>]*href="([^"]+)"[^>]*>\s*<h\d[^>]*>([^<]{5,80})</h\d>',
                    html
                )
                if not items:
                    items = re.findall(
                        r'<a\s+[^>]*href="([^"]+)"[^>]*title="([^"]{5,80})"',
                        html
                    )
                found = 0
                for link_url, title in items[:15]:
                    if title and len(title) >= 4:
                        # 补全相对路径
                        if link_url.startswith("/"):
                            from urllib.parse import urljoin
                            link_url = urljoin(url, link_url)
                        all_sources.append({
                            "title": title[:80],
                            "url": link_url,
                            "snippet": f"{name}：{title}",
                        })
                        found += 1
                print(f"   [领域]   ✅ {name} 获取到 {found} 条")
            except Exception as e:
                print(f"   [领域]   ❌ {name} 爬取失败：{e}")
            time.sleep(0.3)

    # 2. 从 domains_config.json 读取预置数据源（补充）
    json_config = _get_domain_config(domain)
    if json_config:
        json_keywords = json_config.get("search_keywords", [])
        if json_keywords:
            domain_keywords.extend(json_keywords)

        rss_sources = json_config.get("rss_sources", [])
        html_sources = json_config.get("html_sources", [])

        for source in rss_sources[:3]:
            if isinstance(source, str):
                parts = re.split(r"\s*[:：]\s*", source, maxsplit=1)
                if len(parts) == 2 and parts[1].startswith("http"):
                    s_name, s_url = parts[0], parts[1]
                else:
                    continue
            else:
                s_name = source.get("name", "RSS源")
                s_url = source.get("url", "")
            if not s_url or not s_url.startswith("http"):
                continue
            print(f"   [领域] RSS获取 {s_name}...")
            rss_results = _fetch_ithome_rss(s_url, max_results=20)
            all_sources.extend(rss_results)
            time.sleep(0.3)

        for source in html_sources[:2]:
            if isinstance(source, str):
                parts = re.split(r"\s*[:：]\s*", source, maxsplit=1)
                if len(parts) == 2 and parts[1].startswith("http"):
                    s_name, s_url = parts[0], parts[1]
                else:
                    continue
            else:
                s_name = source.get("name", "HTML源")
                s_url = source.get("url", "")
            if not s_url or not s_url.startswith("http"):
                continue
            print(f"   [领域] 爬取 {s_name}...")
            try:
                resp = requests.get(s_url, headers=_rand_headers(), timeout=10)
                resp.encoding = resp.apparent_encoding or "utf-8"
                html = resp.text
                items = re.findall(
                    r'<a\s+[^>]*href="([^"]+)"[^>]*>\s*<h\d[^>]*>([^<]{5,80})</h\d>',
                    html
                )
                if not items:
                    items = re.findall(
                        r'<a\s+[^>]*href="([^"]+)"[^>]*title="([^"]{5,80})"',
                        html
                    )
                for link_url, title in items[:15]:
                    if title and len(title) >= 4:
                        if link_url.startswith("/"):
                            from urllib.parse import urljoin
                            link_url = urljoin(s_url, link_url)
                        all_sources.append({
                            "title": title[:80],
                            "url": link_url,
                            "snippet": f"{s_name}：{title}",
                        })
            except Exception as e:
                print(f"   [领域] {s_name} 爬取失败：{e}")
            time.sleep(0.3)

    # 3. 没有任何数据源时，用搜索引擎补充
    if not all_sources and topic_keywords:
        print(f"   [领域] 无专属数据源，用搜索引擎补充【{', '.join(topic_keywords[:3])}】...")
        ddg_unavailable = False
        for kw in topic_keywords[:3]:
            try:
                results = _duckduckgo_search(kw, max_results=10)
                if results is None:
                    ddg_unavailable = True
                    break
                all_sources.extend(results)
            except Exception as e:
                print(f"   [领域] 搜索失败：{e}")
            time.sleep(1)

    if not all_sources:
        print(f"   [领域] ⚠️  未从任何渠道获取到【{domain}】领域内容")
        return []

    # 去重
    seen = set()
    deduped = []
    for r in all_sources:
        key = r.get("url") or r.get("title", "")
        if key and key not in seen:
            seen.add(key)
            deduped.append(r)

    # 按主题关键词过滤
    all_keywords = topic_keywords + domain_keywords
    if all_keywords:
        keyword_filtered = [
            r for r in deduped
            if any(kw in r["title"] or kw in r.get("snippet", "")
                   for kw in all_keywords)
        ]
        if keyword_filtered:
            print(f"   [领域] 关键词过滤后剩余 {len(keyword_filtered)} 条（总计 {len(deduped)} 条）")
            return keyword_filtered[:max_results]
        else:
            print(f"   [领域] 关键词过滤无匹配，返回全部 {len(deduped)} 条")

    print(f"   [领域] 获取到 {len(deduped)} 条领域内容")
    return deduped[:max_results]


def _fetch_tech_news_legacy(topic_keywords: List[str], max_results: int = 20) -> List[Dict]:
    """
    原来的科技新闻爬虫逻辑（保持向后兼容）。
    聚合多个科技媒体的最新文章，按主题关键词过滤。
    """
    all_results = []

    # IT之家综合 RSS（质量最高，实时更新）
    print("   [爬虫] 获取 IT之家 最新文章...")
    rss_results = _fetch_ithome_rss("https://www.ithome.com/rss/", max_results=30)
    all_results.extend(rss_results)
    time.sleep(0.3)

    # 36氪 RSS
    print("   [爬虫] 获取 36氪 最新文章...")
    kr_results = _fetch_36kr_mobile(max_results=20)
    all_results.extend(kr_results)
    time.sleep(0.3)

    # 快科技（补充更多当天内容）
    print("   [爬虫] 获取 快科技 最新文章...")
    try:
        resp = requests.get("https://www.mydrivers.com/", headers=_rand_headers(), timeout=10)
        resp.encoding = "utf-8"
        html = resp.text

        # 提取新闻标题和链接
        items = re.findall(
            r'<a\s+[^>]*href="([^"]*article[^"]*)"[^>]*title="([^"]{5,80})"',
            html
        )
        for url, title in items[:20]:
            if title and len(title) >= 4 and "mydrivers.com" in url:
                all_results.append({
                    "title": title[:80],
                    "url": url,
                    "snippet": f"快科技报道：{title}",
                })
    except Exception as e:
        print(f"   [快科技] 爬取失败：{e}")

    # 去重
    seen = set()
    deduped = []
    for r in all_results:
        key = r.get("url") or r.get("title", "")
        if key and key not in seen:
            seen.add(key)
            deduped.append(r)

    # 优先过滤当天内容（在标题或摘要中包含今天日期）
    today_str = datetime.now().strftime("%m月%d日")
    today_results = [
        r for r in deduped
        if today_str in r["title"] or today_str in r.get("snippet", "")
    ]

    # 如果当天内容足够，优先使用当天内容
    if len(today_results) >= max_results:
        print(f"   [筛选] 找到 {len(today_results)} 条当天内容，优先使用")
        filtered_sources = today_results
    else:
        print(f"   [筛选] 当天内容不足 {len(today_results)} 条，使用全部内容")
        filtered_sources = deduped

    # 按主题关键词过滤
    if topic_keywords:
        # 提取核心关键词（去掉日期部分，保留主题词）
        import re as regex_module
        core_keywords = []
        for kw in topic_keywords:
            # 去掉日期格式：2026年04月11日、2026年4月、4月11日等
            core = regex_module.sub(r'\d{4}年\d{1,2}月\d{1,2}日?', '', kw)
            core = regex_module.sub(r'\d{4}年\d{1,2}月?', '', core)
            core = regex_module.sub(r'\d{1,2}月\d{1,2}日?', '', core)
            core = core.strip()
            if core and len(core) >= 2:
                core_keywords.append(core)
        
        # 合并原始关键词和核心关键词
        all_keywords = topic_keywords + core_keywords
        
        keyword_filtered = [
            r for r in filtered_sources
            if any(kw in r["title"] or kw in r.get("snippet", "")
                   for kw in all_keywords)
        ]
        if keyword_filtered:
            print(f"   [筛选] 按关键词过滤后剩余 {len(keyword_filtered)} 条")
            return keyword_filtered[:max_results]

    return filtered_sources[:max_results]


# ════════════════════════════════════════════════════════════
# DuckDuckGo HTML 搜索（带退避重试）
# ════════════════════════════════════════════════════════════

def _ddgo_html_search(query: str, max_results: int = 10, retry: int = 3) -> List[Dict]:
    """
    DuckDuckGo HTML 接口搜索（原始可用版本）。
    使用 html.duckduckgo.com/html/ 接口和 result__a 类名解析。
    retry 默认 3 次，超时 12 秒。
    """
    for attempt in range(retry):
        try:
            if attempt > 0:
                wait = random.uniform(3, 6)
                print(f"   [ddgo] 限流，等待 {wait:.1f}s 后重试...")
                time.sleep(wait)

            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query, "kl": "cn-zh", "df": "w"},
                headers=_rand_headers(),
                timeout=12,
            )

            # 202 = 限流/验证页，直接放弃
            if resp.status_code != 200:
                print(f"   [ddgo] 返回状态码 {resp.status_code}，尝试重试...")
                continue

            html = resp.text
            results = []

            # 主正则 - 原始可用版本
            blocks = re.findall(
                r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
                r'class="result__snippet"[^>]*>(.*?)</(?:a|span|div)>',
                html, re.DOTALL,
            )
            for url, raw_title, raw_snip in blocks[:max_results]:
                title   = re.sub(r'<[^>]+>', '', raw_title).strip()
                snippet = re.sub(r'<[^>]+>', '', raw_snip).strip()
                if "duckduckgo.com/l/" in url:
                    m = re.search(r'uddg=([^&]+)', url)
                    if m:
                        url = unquote(m.group(1))
                if title and len(title) >= 4:
                    results.append({
                        "title":   title[:80],
                        "url":     url,
                        "snippet": snippet[:300],
                    })

            # 备用简单正则
            if not results:
                titles   = re.findall(r'class="result__a"[^>]*>([^<]{4,80})', html)
                snippets = re.findall(r'class="result__snippet"[^>]*>([^<]{4,200})', html)
                urls_raw = re.findall(r'class="result__url"[^>]*>([^<]{4,200})', html)
                for i, t in enumerate(titles[:max_results]):
                    results.append({
                        "title":   t.strip(),
                        "url":     urls_raw[i].strip() if i < len(urls_raw) else "",
                        "snippet": snippets[i].strip() if i < len(snippets) else "",
                    })

            if results:
                print(f"   [ddgo] 成功获取 {len(results)} 条结果")
                return results
            else:
                print(f"   [ddgo] 未匹配到搜索结果")

        except requests.exceptions.ConnectionError as e:
            print(f"   [ddgo] 连接失败：{e}")
            if attempt < retry - 1:
                continue
        except requests.exceptions.Timeout:
            print(f"   [ddgo] 请求超时（12s）")
            if attempt < retry - 1:
                continue
        except Exception as e:
            print(f"   [ddgo] 异常：{e}")
            if attempt < retry - 1:
                time.sleep(random.uniform(2, 4))
                continue

    return []


def _bing_search(query: str, max_results: int, api_key: str) -> List[Dict]:
    """Bing Search API v7"""
    try:
        headers = {"Ocp-Apim-Subscription-Key": api_key}
        params  = {"q": query, "count": max_results, "mkt": "zh-CN", "freshness": "Week"}
        resp    = requests.get(BING_SEARCH_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data    = resp.json()
        results = []
        for item in data.get("webPages", {}).get("value", []):
            results.append({
                "title":   item.get("name", ""),
                "url":     item.get("url", ""),
                "snippet": item.get("snippet", ""),
            })
        return results
    except Exception as e:
        print(f"   [bing] 搜索异常：{e}")
        return []


# ════════════════════════════════════════════════════════════
# 热搜数据源（从 hotrank 模块聚合多平台热搜）
# ════════════════════════════════════════════════════════════

def _fetch_hotrank_sources(max_per_platform: int = 10, max_total: int = 50) -> List[Dict]:
    """
    从多个平台抓取热搜数据，转换为统一格式混入选题素材。
    
    选用平台策略：微博/百度/头条/知乎（泛热点）+ IT之家/36氪（科技向）
    返回格式与搜索结果一致：{title, url, snippet}
    """
    from modules.hotrank import PLATFORM_MAP, get_hotrank
    
    # 核心平台列表：覆盖面广 + 时效性强
    core_platform_ids = ["weibo", "baidu", "toutiao", "zhihu", "ithome", "36kr", "bilibili", "douyin"]
    
    all_results = []
    seen_titles = set()
    
    print(f"   [热搜] 抓取 {len(core_platform_ids)} 个平台热搜数据...")
    
    for pid in core_platform_ids:
        platform = PLATFORM_MAP.get(pid)
        if not platform:
            continue
        
        try:
            data = get_hotrank(pid)
            items = data.get("items", [])
            platform_name = platform["name"]
            
            count = 0
            for item in items[:max_per_platform]:
                title = item.get("title", "").strip()
                url = item.get("url", "")
                hot_val = item.get("hot", "")
                
                if not title or len(title) < 4:
                    continue
                # 去重
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                
                # 热度信息作为 snippet
                hot_info = f"热度 {hot_val}" if hot_val else f"{platform_name}热搜第{item.get('rank', '?')}位"
                
                all_results.append({
                    "title": title[:80],
                    "url": url,
                    "snippet": f"【{platform_name}热搜】{hot_info}",
                    "_is_hotrank": True,  # 标记来源，供后续参考
                    "_source_platform": platform_name,
                })
                count += 1
                
                if len(all_results) >= max_total:
                    break
            
            if count > 0:
                print(f"      {platform_name}: 获取 {count} 条")
            
            if len(all_results) >= max_total:
                break
                
        except Exception as e:
            print(f"      [热搜/{platform.get('name', pid)}] 抓取失败: {e}")
        
        # 平台间加小延迟，避免并发过高
        time.sleep(0.2)
    
    print(f"   [热搜] 共获取 {len(all_results)} 条热搜数据")
    return all_results


# ════════════════════════════════════════════════════════════
# 选题生成（主入口）
# ════════════════════════════════════════════════════════════

def generate_topics(
    prompt: str,
    domain: str = "",
    search_queries: Optional[List[str]] = None,
    max_topics: int = 10,
    cache_hours: float = 6.0,
    user_id: int = None,
) -> List[Dict]:
    """
    根据自定义提示词，先 AI 分析关键词 → 搜索引擎获取真实新闻 → AI 整理成选题。
    不依赖固定网站爬虫，完全由提示词驱动。

    流程：
        1. AI 从 topic_prompt 中分析出搜索关键词（降级：正则提取）
        2. 用关键词搜索（Bing API → DuckDuckGo → 国内领域媒体源）
        3. AI 将搜索结果整理成结构化选题（降级：传统格式化）
        4. AI 打分排序

    Args:
        prompt:         用户自定义选题提示词（描述方向、筛选标准）
        domain:         账号领域（仅作为 AI 上下文提示，不再用于选择固定爬虫）
        search_queries: 外部传入的搜索关键词（若提供则跳过 AI/正则提取）
        max_topics:     最多返回几条选题
        cache_hours:    缓存时长（小时）。0 = 强制重新获取
        user_id:       用户 ID（用于选择用户的默认 AI 模型）

    Returns:
        [{"rank", "title", "summary", "detail", "source_url", "is_hot"}]
    """
    today     = datetime.now().strftime("%Y%m%d")
    cache_key = hashlib.md5(f"{prompt}_{domain}_{today}".encode()).hexdigest()[:12]
    cache_file = CACHE_DIR / f"topics_{cache_key}.json"

    # 读缓存
    if cache_hours > 0 and cache_file.exists():
        age = (time.time() - cache_file.stat().st_mtime) / 3600
        if age < cache_hours:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached:
                print(f"   [cache] 命中选题缓存（{age:.1f}h 前生成，共 {len(cached)} 条）")
                return cached

    # ── Step 1：分析搜索关键词 ──────────────────────────────
    domain_hint = f"【{domain}】" if domain else ""
    print(f"   [1/3] 分析{domain_hint}选题关键词...")

    if search_queries:
        # 外部传入，直接使用
        print(f"   🔎 使用传入的搜索关键词：{search_queries}")
    else:
        # 优先 AI 提取
        search_queries = _ai_extract_search_queries(prompt, domain, user_id)
        if not search_queries:
            # 降级：正则提取
            search_queries = _extract_search_queries_fallback(prompt, domain)
            print(f"   🔎 正则提取搜索关键词：{search_queries}")

    # ── Step 2：搜索引擎获取当天真实新闻 + 热搜数据补充 ─────────
    print(f"   [2/3] 搜索获取当天最新内容（共 {len(search_queries)} 个关键词）...")

    raw_results: List[Dict] = []
    bing_key = os.environ.get("BING_SEARCH_KEY", "")
    ddg_unavailable = False  # DDG 不可用标记，后续直接跳过

    for i, q in enumerate(search_queries):
        print(f"      搜索：{q}")

        # 优先 Bing API（有配置时质量最好）
        if bing_key:
            results = _bing_search(q, max_results=10, api_key=bing_key)
            if results:
                raw_results.extend(results)
                time.sleep(0.2)
                continue  # Bing API 拿到了，跳过 DDG

        # DuckDuckGo（主力搜索引擎）
        if not ddg_unavailable:
            ddg_results = _ddgo_html_search(q, max_results=10)
            if ddg_results:
                raw_results.extend(ddg_results)
            else:
                # DDG 返回空，标记不可用，后续关键词不再尝试
                if not raw_results:
                    print(f"      [info] DuckDuckGo 不可用（网络不可达），降级到国内媒体源...")
                ddg_unavailable = True

        # DDG 不可用时，跳过剩余关键词的搜索（因为无法搜索）
        if ddg_unavailable:
            print(f"      [info] DuckDuckGo 不可用，跳过剩余关键词搜索")
            break

        # 关键词间加随机延迟，防止限流
        if i < len(search_queries) - 1 and not ddg_unavailable:
            time.sleep(random.uniform(1.5, 2.5))

    # ── Step 2.5：补充热搜数据 ──────────────────────────────
    hotrank_results = _fetch_hotrank_sources(max_per_platform=10, max_total=50)

    if hotrank_results:
        # 用领域/提示词关键词过滤热搜，去掉不相关的泛资讯
        filter_kws = _build_hotrank_filter_keywords(prompt, domain)
        if filter_kws:
            before_count = len(hotrank_results)
            hotrank_results = _filter_hotrank_by_keywords(hotrank_results, filter_kws)
            after_count = len(hotrank_results)
            if before_count > after_count:
                print(f"   [热搜] 按关键词过滤：{before_count} → {after_count} 条（关键词：{', '.join(filter_kws[:5])}）")

        # 热搜去重合并到搜索结果中
        seen = {r.get("url") or r.get("title", "") for r in raw_results}
        added_count = 0
        for hr in hotrank_results:
            key = hr.get("url") or hr.get("title", "")
            if key and key not in seen:
                raw_results.append(hr)
                seen.add(key)
                added_count += 1
        
        if added_count > 0:
            print(f"   [热搜] 新增 {added_count} 条热搜素材（去重后总计 {len(raw_results)} 条）")

    # ── Step 2.6：补充领域网站数据 ──────────────────────────
    if domain:
        print(f"   [领域] 爬取【{domain}】领域专属网站...")
        domain_results = _fetch_domain_news(domain, search_queries or [], max_results=20)
        if domain_results:
            seen_domain = {r.get("url") or r.get("title", "") for r in raw_results}
            added_domain = 0
            for dr in domain_results:
                key = dr.get("url") or dr.get("title", "")
                if key and key not in seen_domain:
                    raw_results.append(dr)
                    seen_domain.add(key)
                    added_domain += 1
            if added_domain > 0:
                print(f"   [领域] 新增 {added_domain} 条领域素材（去重后总计 {len(raw_results)} 条）")
        else:
            print(f"   [领域] 未从领域网站获取到内容")

    # 搜索+热搜都不可用时，使用AI大模型根据提示词生成选题
    if ddg_unavailable and len(raw_results) < 5 and not hotrank_results:
        print(f"   [info] 搜索引擎不可用且无热搜数据，使用AI大模型根据提示词生成选题...")
        
        # 使用AI大模型根据用户提示词直接生成选题
        ai_topics = _ai_generate_topics_from_prompt(prompt, domain, max_topics, user_id)
        if ai_topics:
            print(f"   [info] AI大模型生成 {len(ai_topics)} 条选题")
            # 对AI生成的选题进行评分排序
            ai_topics = ai_enhance_topics(ai_topics, prompt, domain, max_to_score=len(ai_topics))
            return ai_topics

    # 全局去重
    seen = set()
    deduped = []
    for r in raw_results:
        key = r.get("url") or r.get("title", "")
        if key and key not in seen:
            seen.add(key)
            deduped.append(r)

    print(f"   去重后：{len(deduped)} 条原始结果")

    # 时间过滤：丢弃有日期但超过 3 天的旧内容；无法判断日期的条目（热搜等）始终保留
    filtered = _filter_recent_results(deduped, days=3)
    dated_old = len(deduped) - len(filtered)
    if dated_old > 0:
        print(f"   [时间过滤] 已丢弃 {dated_old} 条超过 3 天的过时内容，剩余 {len(filtered)} 条")
    else:
        print(f"   [时间过滤] 全部 {len(filtered)} 条（无过时内容）")
    deduped = filtered

    # 搜索结果不足时给出提示
    if len(deduped) < 3:
        print("   ⚠️  搜索结果较少，可能受搜索引擎限流影响，继续尝试 AI 整理...")

    # ── Step 3：AI 整理成选题 ──────────────────────────────
    print("   [3/3] AI 整理搜索结果成选题...")
    topics = _ai_organize_news_to_topics(deduped, prompt, domain, max_topics, user_id)

    if topics:
        print(f"   ✅ AI 整理成功，共 {len(topics)} 条选题")
        # 后处理：清除 AI 脑补的素材中不存在的日期
        topics = _strip_fabricated_year_month(topics, deduped)
    else:
        print("   ⚠️  AI 整理失败，降级到传统格式化方式...")
        topic_keywords = _extract_topic_keywords(prompt)
        topics = _format_topics(deduped, topic_keywords, max_topics)

        if not topics and topic_keywords:
            print("   主题过滤后无结果，放宽过滤...")
            topics = _format_topics(deduped, [], max_topics)

    if not topics:
        print("   ⚠️  未能获取到有效选题")
        return []

    # ── Step 4：AI 打分排序 ──────────────────────────────
    topics = ai_enhance_topics(topics, prompt, domain, max_to_score=8)

    # 写缓存
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)

    return topics


# ════════════════════════════════════════════════════════════
# 关键词提取工具函数
# ════════════════════════════════════════════════════════════

def _ai_extract_search_queries(prompt: str, domain: str = "", user_id: int = None) -> Optional[List[str]]:
    """
    使用 AI 从选题提示词中分析出最适合的搜索关键词。
    返回 2-4 个查询词，每个可直接输入搜索引擎。
    如果 AI 不可用返回 None，由调用方降级到正则。

    Args:
        prompt: 用户选题提示词
        domain: 账号领域（可选）
        user_id: 用户 ID（用于选择用户的默认 AI 模型）
    """
    backend, config = _detect_llm_backend(user_id)
    if backend == "template":
        return None

    today = datetime.now().strftime("%Y年%m月%d日")
    today_month = datetime.now().strftime("%Y年%m月")
    current_year = datetime.now().year

    # 完全依赖用户 prompt，domain 仅作背景参考
    domain_hint = f"（领域参考：{domain}）" if domain else ""
    extract_prompt = f"""你是搜索关键词专家。根据下面的「内容方向描述」，生成 3-4 个最适合搜索引擎的中文查询词。

今天是 {today}{domain_hint}

## 内容方向描述
{prompt}

## 要求
1. 每个查询词要精准，能搜到当天最新内容
2. 优先包含时间词（如"{today_month}"）
3. **重要：当前年份是{current_year}年，禁止生成任何包含{current_year}年以后日期的关键词（如禁止"{current_year+1}年"、"{current_year}年12月31日之后"等）**
4. 覆盖描述中提到的核心话题，不同查询词要有差异化
5. 查询词控制在 5-15 字，太长搜不到结果
6. 禁止输出元描述词（如"最新动态"、"热门话题"等空泛词）
7. 如果提示词涉及特定领域（如汽车、手机），确保关键词与该领域强相关

## 输出格式
只输出一个 JSON 数组，不要任何解释，例如：
["新能源汽车 销量 {today_month}", "比亚迪 特斯拉 价格战", "汽车 智能驾驶 新政策"]
"""

    try:
        if backend == "openai":
            from modules.ai_writer import _call_openai
            resp = _call_openai(extract_prompt, config)
        elif backend == "ollama":
            from modules.ai_writer import _call_ollama
            resp = _call_ollama(extract_prompt, config)
        else:
            return None

        resp = resp.strip()
        # 提取 JSON 数组
        arr_match = re.search(r'\[.*\]', resp, re.DOTALL)
        if arr_match:
            queries = json.loads(arr_match.group(0))
            if isinstance(queries, list):
                # 过滤空字符串和过短的词
                queries = [q.strip() for q in queries if isinstance(q, str) and len(q.strip()) >= 3]
                # 后处理：移除包含未来日期的关键词
                current_date = datetime.now()
                current_year = current_date.year
                filtered_queries = []
                for q in queries:
                    # 检查是否包含未来年份（当前年份+1及以上）
                    import re as regex_module
                    year_matches = regex_module.findall(r'(\d{4})年', q)
                    has_future_date = False
                    for year_str in year_matches:
                        try:
                            year = int(year_str)
                            if year > current_year:
                                # 未来年份，过滤
                                has_future_date = True
                                print(f"   ⚠️  过滤掉包含未来年份的关键词：{q}")
                                break
                            elif year == current_year:
                                # 同年，检查是否包含未来月份和日期
                                # 匹配模式：2026年04月11日 或 2026年4月
                                full_date_match = regex_module.search(r'{year}年(\d{{1,2}})月(\d{{1,2}})日'.format(year=year), q)
                                if full_date_match:
                                    month = int(full_date_match.group(1))
                                    day = int(full_date_match.group(2))
                                    if month > current_date.month or (month == current_date.month and day > current_date.day):
                                        has_future_date = True
                                        print(f"   ⚠️  过滤掉包含未来日期的关键词：{q}")
                                        break
                                # 检查只有月份的情况：2026年4月
                                month_only_match = regex_module.search(r'{year}年(\d{{1,2}})月'.format(year=year), q)
                                if month_only_match and not full_date_match:
                                    month = int(month_only_match.group(1))
                                    if month > current_date.month:
                                        has_future_date = True
                                        print(f"   ⚠️  过滤掉包含未来月份的关键词：{q}")
                                        break
                        except ValueError:
                            continue
                    if not has_future_date:
                        filtered_queries.append(q)
                queries = filtered_queries
                if queries:
                    print(f"   🤖 AI 分析关键词：{queries}")
                    return queries[:4]
    except Exception as e:
        print(f"   ⚠️  AI 提取关键词失败：{e}")

    return None


def _extract_search_queries_fallback(prompt: str, domain: str = "") -> List[str]:
    """
    正则降级方案：从提示词中提取搜索关键词（AI 不可用时使用）
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    today_month = datetime.now().strftime("%Y年%m月")

    bracket_matches = re.findall(r'[【\[]([^\]】]{2,20})[】\]]', prompt)
    skip_words = {"方向", "标准", "格式", "内容", "输出", "以下", "动态",
                  "当天", "条", "重点", "覆盖", "筛选", "优先", "最值得关注"}
    base_keywords = [
        m for m in bracket_matches
        if not any(s in m for s in skip_words) and len(m) >= 2
    ]

    if base_keywords:
        queries = [f"{' '.join(base_keywords[:3])} {today_month} 最新"]
        for kw in base_keywords[:2]:
            queries.append(f"{kw} 最新资讯 {today_month}")
        return queries[:4]

    lines = [l.strip() for l in prompt.split('\n') if l.strip()]
    queries = []
    for line in lines[:3]:
        clean = re.sub(
            r'[【】：:（）()、。，,\d+请你整理最值得关注条动态重点覆盖以下方向筛选标准]',
            ' ', line
        ).strip()
        clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) > 3:
            queries.append(f"{clean[:20]} {today_month}")

    return queries[:4] if queries else [f"{domain}热点 {today_month}"]


def _extract_topic_keywords(prompt: str) -> List[str]:
    """从 prompt 中提取主题词，用于过滤无关搜索结果（仅用于传统爬虫模式兜底）"""
    skip_words = {
        "方向", "标准", "格式", "内容", "输出", "以下", "动态", "当天", "今天", "今日",
        "重点", "覆盖", "筛选", "优先", "最值", "关注", "领域", "条", "整理", "请你",
        "选题", "信息量", "发生", "小时", "新增",
    }

    bracket_kws = re.findall(r'[【\[]([^\]】]{1,8})[】\]]', prompt)
    kws = []
    for raw in bracket_kws:
        cleaned = re.sub(r'(今天|当天|今日|最新|领域|方向|最值得关注|\d+条)', '', raw).strip()
        if cleaned and len(cleaned) >= 2 and cleaned not in skip_words:
            kws.append(cleaned)

    seen = set()
    result = []
    for k in kws:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result[:2]


def _build_hotrank_filter_keywords(prompt: str, domain: str) -> List[str]:
    """
    构建热搜过滤关键词列表。用于在热搜数据进 AI 之前过滤掉与领域/需求无关的条目。
    优先从领域配置的 search_keywords 读取，其次从 prompt 中提取，最后用 domain 名称。
    """
    # 1. 领域配置的关键词（最精准）
    domain_config = _get_domain_config(domain) if domain else {}
    domain_kws = domain_config.get("search_keywords", [])
    if domain_kws:
        return domain_kws[:10]

    # 2. 从 prompt 提取
    prompt_kws = _extract_topic_keywords(prompt)
    if prompt_kws:
        return prompt_kws

    # 3. 用 domain 名称本身作为关键词
    if domain and len(domain) >= 2:
        return [domain]

    return []


def _filter_hotrank_by_keywords(hotrank_results: List[Dict], filter_kws: List[str]) -> List[Dict]:
    """
    用关键词过滤热搜结果，只保留至少命中一个关键词的条目。
    如果没有关键词（无领域无提示词），则不过滤（保留全部）。
    """
    if not filter_kws:
        return hotrank_results

    filtered = []
    for item in hotrank_results:
        title = item.get("title", "")
        if any(kw in title for kw in filter_kws):
            filtered.append(item)

    return filtered


# ════════════════════════════════════════════════════════════
# 格式化选题
# ════════════════════════════════════════════════════════════

def _filter_recent_results(results: List[Dict], days: int = 3) -> List[Dict]:
    """
    过滤出近 N 天内有明确日期的搜索结果。
    - 能从标题/摘要检测到日期的条目：只保留近期（<= days 天）的
    - 无法检测到日期的条目：直接丢弃（无法判断时效性）
    """
    from datetime import timedelta
    now = datetime.now()
    cutoff = now - timedelta(days=days)

    recent = []

    for r in results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        combined = f"{title} {snippet}"

        # 提取日期字符串
        found_dates = _extract_dates_from_text(combined)
        if found_dates:
            # 取最近的一个日期，只保留近期（<= days 天）的
            latest = max(found_dates)
            if latest >= cutoff:
                recent.append(r)
            # 有日期但超出范围 → 丢弃
        # 无日期的搜索结果直接丢弃（无法判断时效性，不应混入）

    return recent


def _strip_fabricated_year_month(topics: List[Dict], source_results: List[Dict]) -> List[Dict]:
    """
    后处理校验：从 AI 生成的选题中清除素材里没有出现的事实性时间描述。
    防止 AI 用"今日""昨天""刚刚"等模糊时间掩盖真实日期，或脑补素材中不存在的年月日。
    """
    # 收集素材中实际出现的所有日期信息
    source_year_months = set()  # (年, 月) 组合
    source_year_month_days = set()  # (年, 月, 日) 组合
    source_dates_raw = set()  # 原始日期字符串

    for r in source_results:
        combined = f"{r.get('title', '')} {r.get('snippet', '')}"
        # 提取 YYYY年M月D日
        for m in re.finditer(r'(\d{4})年(\d{1,2})月(\d{1,2})日?', combined):
            try:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                source_year_months.add((y, mo))
                source_year_month_days.add((y, mo, d))
                source_dates_raw.add(m.group(0))
            except ValueError:
                pass
        # 提取 M月D日（无年份）
        for m in re.finditer(r'(?<!\d)(\d{1,2})月(\d{1,2})日', combined):
            try:
                mo, d = int(m.group(1)), int(m.group(2))
                if 1 <= mo <= 12 and 1 <= d <= 31:
                    source_year_months.add((datetime.now().year, mo))
                    source_year_month_days.add((datetime.now().year, mo, d))
                    source_dates_raw.add(m.group(0))
            except ValueError:
                pass

    # 需要替换的模糊时间词（AI常用这些来掩盖日期错误）
    fuzzy_time_patterns = [
        (r'今日\s*正式', '正式'),        # "今日正式上市" → "正式上市"
        (r'今日\s*', ''),               # "今日发布" → "发布"
        (r'昨天\s*正式', '正式'),
        (r'昨天\s*', ''),
        (r'昨日\s*正式', '正式'),
        (r'昨日\s*', ''),
        (r'刚刚\s*', ''),
        (r'刚刚\w*了', ''),
        (r'日前\s*', ''),
        (r'近期\s*正式', '正式'),
    ]

    def clean_text(text: str) -> str:
        if not text:
            return text
        cleaned = text

        # 1. 清除模糊时间词（"今日""昨天""刚刚"等）
        for pattern, replacement in fuzzy_time_patterns:
            cleaned = re.sub(pattern, replacement, cleaned)

        # 2. 清除素材中不存在的 YYYY年M月D日
        for m in re.finditer(r'(\d{4})年(\d{1,2})月(\d{1,2})日?', cleaned):
            try:
                y, mo = int(m.group(1)), int(m.group(2))
                if (y, mo) not in source_year_months:
                    cleaned = cleaned.replace(m.group(0), "", 1)
            except ValueError:
                pass

        # 3. 清除素材中不存在的 M月D日
        for m in re.finditer(r'(?<!\d)(\d{1,2})月(\d{1,2})日', cleaned):
            try:
                mo, d = int(m.group(1)), int(m.group(2))
                if 1 <= mo <= 12 and 1 <= d <= 31:
                    if (datetime.now().year, mo, d) not in source_year_month_days:
                        cleaned = cleaned.replace(m.group(0), "", 1)
            except ValueError:
                pass

        return cleaned.strip()

    cleaned_count = 0
    for topic in topics:
        for field in ("title", "summary", "detail"):
            original = topic.get(field, "")
            new_val = clean_text(original)
            if new_val != original:
                topic[field] = new_val
                cleaned_count += 1

    if cleaned_count > 0:
        print(f"   [反幻觉] 清除 {cleaned_count} 处素材中不存在的时间描述")

    return topics


def _extract_dates_from_text(text: str) -> List[datetime]:
    """
    从文本中提取所有日期，返回 datetime 列表。
    支持格式：
    - 2026年4月9日 / 2026年04月09日
    - 4月9日 / 04月09日
    - 2026-04-09 / 2026.04.09
    - 今天 / 昨天
    """
    from datetime import timedelta
    now = datetime.now()
    dates = []
    current_year = now.year

    # 格式1：YYYY年M月D日 或 YYYY年MM月DD日
    for m in re.finditer(r'(\d{4})年(\d{1,2})月(\d{1,2})日?', text):
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            dates.append(datetime(y, mo, d))
        except ValueError:
            pass

    # 格式2：M月D日 或 MM月DD日（无年份，默认当年）
    for m in re.finditer(r'(?<!\d)(\d{1,2})月(\d{1,2})日', text):
        try:
            mo, d = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                dates.append(datetime(current_year, mo, d))
        except ValueError:
            pass

    # 格式3：YYYY-MM-DD 或 YYYY.MM.DD
    for m in re.finditer(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', text):
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            dates.append(datetime(y, mo, d))
        except ValueError:
            pass

    # 格式4："今天"/"昨日"/"昨天"
    if "今天" in text or "今日" in text:
        dates.append(now)
    if "昨天" in text or "昨日" in text:
        dates.append(now - timedelta(days=1))

    # 格式5：X小时前 / X分钟前
    for m in re.finditer(r'(\d+)\s*小时前', text):
        try:
            hours = int(m.group(1))
            dates.append(now - timedelta(hours=hours))
        except ValueError:
            pass
    for m in re.finditer(r'(\d+)\s*分钟前', text):
        dates.append(now)

    return dates


def _format_topics(
    raw_results: List[Dict],
    topic_keywords: List[str],
    max_topics: int,
) -> List[Dict]:
    """将原始搜索结果过滤 + 格式化为选题列表，当天内容优先"""
    topics = []
    today_full = datetime.now().strftime("%Y年%m月%d日")
    today_short = datetime.now().strftime("%m月%d日")

    hot_keywords = [
        "发布", "官宣", "最新", "首发", "突破", "涨价", "降价",
        "推出", "上线", "宣布", "曝光", "爆料", "预售",
        "新款", "升级", "评测", "对比", "体验", "旗舰", "新机",
    ]

    # 先处理当天内容，再处理近3天内容，最后其他内容
    today_items = []
    recent_items = []  # 近3天但非当天
    other_items = []

    for r in raw_results:
        title   = r.get("title", "").strip()
        snippet = r.get("snippet", "").strip()
        url     = r.get("url", "")

        if not title or len(title) < 4:
            continue
        if re.search(r'^(搜索失败|Bing 搜索失败|\s*)$', title):
            continue

        # 主题过滤
        if topic_keywords:
            combined = title + snippet
            if not any(kw in combined for kw in topic_keywords):
                continue

        title   = re.sub(r'\s+', ' ', title).strip()[:80]
        combined = title + snippet
        is_hot  = any(kw in combined for kw in hot_keywords)

        # 检测日期时效性
        found_dates = _extract_dates_from_text(combined)
        is_today = (
            today_full in title or today_full in snippet or
            today_short in title or today_short in snippet
        )

        # 如果能检测到日期，检查是否过期（超过7天）
        from datetime import timedelta
        cutoff_7d = datetime.now() - timedelta(days=7)
        if found_dates:
            latest = max(found_dates)
            if latest < cutoff_7d:
                continue  # 超过7天的旧闻直接排除

        is_recent = False
        if found_dates and not is_today:
            cutoff_3d = datetime.now() - timedelta(days=3)
            latest = max(found_dates)
            is_recent = latest >= cutoff_3d

        item = {
            "title":      title,
            "summary":    snippet[:150] if snippet else title,
            "detail":     snippet,
            "source_url": url,
            "is_hot":     is_hot,
            "date":       today_full if is_today else ("近3天" if is_recent else "近期"),
            "is_today":   is_today,
        }

        if is_today:
            today_items.append(item)
        elif is_recent:
            recent_items.append(item)
        else:
            other_items.append(item)

    # 当天内容优先，然后近3天，最后其他（最多取2条其他内容作为兜底）
    all_items = today_items + recent_items + other_items[:2]

    rank = 1
    for item in all_items:
        item["rank"] = rank
        topics.append(item)
        rank += 1
        if rank > max_topics:
            break

    print(f"   [筛选] 当天内容：{len(today_items)} 条，其他内容：{len(other_items[:max_topics-len(today_items)])} 条")
    return topics


# ════════════════════════════════════════════════════════════
# AI 选题增强（当有可用 LLM 时）
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
# AI 选题生成（主入口）
# ════════════════════════════════════════════════════════════

def _ai_organize_news_to_topics(
    news_list: List[Dict],
    prompt: str,
    domain: str = "",
    max_topics: int = 10,
    user_id: int = None
) -> Optional[List[Dict]]:
    """
    使用 AI 将爬取的真实新闻整理成结构化选题。
    保证所有选题都基于当天真实新闻，不是编造的。

    Args:
        news_list:   爬取到的原始新闻列表
        prompt:      用户选题提示词（AI 完全根据此提示词判断相关性，domain 仅为辅助提示）
        domain:      账号领域（可选，仅作为 AI 背景信息，不决定内容方向）
        max_topics:  最多整理几条选题
        user_id:    用户 ID（用于选择用户的默认 AI 模型）

    Returns:
        选题列表，如果 AI 不可用或处理失败则返回 None
    """
    backend, config = _detect_llm_backend(user_id)
    if backend == "template":
        print("   ⚠️  未检测到可用 LLM，跳过 AI 整理")
        return None

    domain_hint = f"【{domain}】" if domain else ""
    print(f"   🤖 使用 {backend} 整理{domain_hint}真实新闻成选题...")

    today_full = datetime.now().strftime("%Y年%m月%d日")
    today_short = datetime.now().strftime("%m月%d日")
    from datetime import timedelta
    cutoff_date = (datetime.now() - timedelta(days=3)).strftime("%Y年%m月%d日")

    # 准备新闻素材（只取前 40 条，避免 token 超限）
    news_items = []
    hotrank_count = 0
    for item in news_list[:40]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        url = item.get("url", "")
        if title and len(title) >= 4:
            # 标记热搜来源
            source_tag = ""
            if item.get("_is_hotrank"):
                source_tag = f"【🔥热搜/{item.get('_source_platform', '热榜')}】"
                hotrank_count += 1
            news_items.append(f"- {source_tag}标题：{title}\n  摘要：{snippet}\n  链接：{url}")

    news_text = "\n\n".join(news_items)

    # 构建整理提示词（完全依赖用户 prompt，domain 仅作背景参考）
    domain_context = f"（账号领域参考：{domain}）" if domain else ""
    hotrank_hint = f"\n## 热搜数据说明\n以上素材中标注了【🔥热搜】的条目来自微博/百度/知乎/头条等平台的热搜榜单，代表当前全网最热门的话题。**如果热搜话题与用户需求相关，请优先选用并适当提高其选题权重，因为这类话题天然具有更高的关注度和传播潜力。**" if hotrank_count > 0 else ""

    # 加载运营规范作为首要参考
    guidelines = _load_operating_guidelines(user_id)
    guidelines_section = f"""
## 运营规范（最高优先级）
你必须严格遵循以下规范进行选题筛选和内容判断：

{guidelines}

**重要：以上运营规范是你判断选题是否合适的最高准则。如果候选新闻素材违反上述任何一条规范（如：过时信息、不实信息、低创作度内容等），必须直接排除。**
""" if guidelines else ""

    organize_prompt = f"""你是专业的内容编辑{domain_context}，任务是将以下真实新闻整理成{max_topics}条精选选题。
{guidelines_section}
## 今天是 {today_full}

## 重要原则
✅ 必须基于提供的真实新闻整理，绝对不要编造
✅ **时效性是第一优先级！只选择 {cutoff_date} 之后（近 3 天内）发生的新闻，超过 3 天的旧闻一律不要**
✅ 优先选择有"今日"、"刚刚"、"官宣"、"发布"等字样的新闻
✅ 相关性完全根据下方「用户需求」判断，不要用领域标签限制范围
✅ **热搜榜单上的话题如果与用户需求匹配，应优先考虑——它们自带流量基础**
❌ **严禁选择超过 3 天的旧闻，素材中标注日期早于 {cutoff_date} 的条目必须排除**
❌ 不要猜测性内容（除非官方确认）
❌ **严禁脑补日期、数字、价格等事实信息！素材中没提到的具体日期/数据，一律不要写进选题的 summary 和 detail 中。如果素材只提到"智己LS8上市"但没有具体日期，就写"智己LS8上市"，绝对不能自己推断成今天。**
❌ **严禁为素材补充未出现的年份信息！如果素材标题是"新一轮国补细则落地"，不要脑补成"2025年12月"或任何历史日期，就写"新一轮国补细则落地"即可。素材写了什么年份就用什么年份，没写年份就不要加。**

## 用户需求
{prompt}

## 待整理的真实新闻素材
{news_text}
{hotrank_hint}

## 输出格式要求
请直接输出一个 JSON 数组，不要任何解释。每条选题包含：
- title: 标题（简洁有力，不超过 40 字）
- summary: 摘要（1-2 句话，不超过 100 字）
- detail: 详细信息（不超过 200 字）
- source_url: 来源链接（从素材中提取）
- is_hot: 是否为热点（true/false）

## 筛选标准
1. **时效性（最重要）**：只选 {cutoff_date} 之后的内容，拒绝任何旧闻
2. 信息量：有新进展、新数据、新产品
3. 热度：发布、官宣、预售、开售等
4. 相关性：完全按照用户需求判断，不受账号领域标签限制

示例输出格式：
[
  {{
    "title": "华为 Pura 80 系列影像规格今日曝光",
    "summary": "{today_short}供应链消息显示...",
    "detail": "详细信息...",
    "source_url": "https://...",
    "is_hot": true
  }}
]

现在请整理：
"""
    
    try:
        if backend == "openai":
            from modules.ai_writer import _call_openai
            response = _call_openai(organize_prompt, config)
        elif backend == "ollama":
            from modules.ai_writer import _call_ollama
            response = _call_ollama(organize_prompt, config)
        else:
            return None
        
        # 解析 JSON
        response = response.strip()
        
        # 尝试提取 JSON 部分（可能包含在代码块中）
        json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
        if json_match:
            response = json_match.group(0)
        
        topics_raw = json.loads(response)
        
        if not isinstance(topics_raw, list):
            print(f"   ⚠️  AI 返回格式错误，不是数组")
            return None
        
        # 格式化选题
        topics = []
        for i, t in enumerate(topics_raw[:max_topics], 1):
            if not isinstance(t, dict):
                continue
            
            title = t.get("title", "").strip()
            if not title or len(title) < 4:
                continue
            
            # 从原始新闻素材中匹配 source_url
            source_url = t.get("source_url", "")
            if not source_url and news_list:
                # 尝试从标题匹配 URL
                for news in news_list:
                    if news.get("title", "") in title or title in news.get("title", ""):
                        source_url = news.get("url", "")
                        break
            
            topics.append({
                "rank":       i,
                "title":      title[:80],
                "summary":    t.get("summary", title)[:150],
                "detail":     t.get("detail", t.get("summary", ""))[:200],
                "source_url": source_url,
                "is_hot":     t.get("is_hot", False),
                "ai_score":   0.0,  # 后续可能会被 ai_enhance_topics 更新
            })
        
        if topics:
            # 给 AI 生成的选题添加基础分数（用于后续排序）
            for i, topic in enumerate(topics):
                topic["ai_score"] = 10.0 - i * 0.5  # 越靠前分数越高
        
        return topics if topics else None
        
    except json.JSONDecodeError as e:
        print(f"   ⚠️  AI 返回 JSON 解析失败：{e}")
        print(f"   原始响应：{response[:200]}...")
        return None
    except Exception as e:
        print(f"   ⚠️  AI 整理新闻异常：{e}")
        return None


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
        print(f"   [选题] 从数据库读取模型失败：{e}")

    return None


def _detect_llm_backend(user_id: int = None) -> Tuple[str, dict]:
    """
    检测可用的 LLM 后端（与 ai_writer 逻辑一致）。

    Args:
        user_id: 用户 ID（用于选择用户的默认 AI 模型）
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

    # 读取 config.json
    config_path = BASE_DIR / "config.json"
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}

    # 2. 从 config.json 读取（向后兼容）
    config_key  = cfg.get("ai_api_key", "").strip()
    config_base = cfg.get("ai_api_base", "").strip()
    config_model = cfg.get("ai_model", "").strip()
    if config_key:
        api_base = config_base or "https://api.openai.com/v1"
        model    = config_model or "deepseek-chat"
        return "openai", {"api_key": config_key, "api_base": api_base, "model": model}
    
    # 2. 从环境变量读取
    api_key  = os.environ.get("AI_API_KEY", "").strip()
    api_base = os.environ.get("AI_API_BASE", "https://api.openai.com/v1")
    model    = os.environ.get("AI_MODEL", "gpt-4o-mini")
    if api_key:
        return "openai", {"api_key": api_key, "api_base": api_base, "model": model}
    
    # 3. Ollama 本地
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
    
    # 4. 无可用 LLM
    return "template", {}


def _ai_generate_topics_from_prompt(prompt: str, domain: str = "", max_topics: int = 10, user_id: int = None) -> Optional[List[Dict]]:
    """
    当搜索引擎不可用时，使用AI大模型根据用户提示词直接生成选题。
    AI会根据提示词的内容，生成符合用户需求的选题列表。
    """
    backend, config = _detect_llm_backend(user_id)
    if backend == "template":
        print("   ⚠️  未检测到可用 LLM，无法生成选题")
        return None
    
    domain_hint = f"【{domain}】" if domain else ""
    print(f"   🤖 使用 {backend} 根据提示词生成{domain_hint}选题...")
    
    today_full = datetime.now().strftime("%Y年%m月%d日")
    today_short = datetime.now().strftime("%m月%d日")
    
    generate_prompt = f"""你是专业的内容编辑，请根据用户的需求，直接生成 {max_topics} 条精选选题。

## 今天是 {today_full}

## 重要原则
✅ 选题必须完全符合用户的需求描述
✅ 选题应该有新闻价值、时效性或实用性
✅ 优先选择有具体信息点的选题（新产品、新技术、新政策、新数据等）
✅ 选题应该适合写成一篇完整的文章
❌ 不要生成过于宽泛或空泛的选题
❌ 不要生成与用户需求无关的选题
❌ **严禁脑补具体日期、数字、价格等事实信息！如果不确定某件事的确切日期或数据，就只描述事件本身，不要猜测。例如不知道上市日期就说"即将上市"或"近期上市"，绝不能编造一个具体日期。**

## 用户需求
{prompt}

## 输出格式要求
请直接输出一个 JSON 数组，不要任何解释。每条选题包含：
- title: 标题（简洁有力，不超过 40 字）
- summary: 摘要（1-2 句话，不超过 100 字）
- detail: 详细信息（不超过 200 字，包含具体信息点）
- source_url: 来源链接（如果有具体来源，否则留空字符串）
- is_hot: 是否为热点（true/false，根据时效性和重要性判断）

## 选题质量要求
1. 相关性：完全符合用户需求
2. 信息量：有新进展、新数据、新产品、新观点
3. 时效性：优先近期内容
4. 实用性：对读者有价值

示例输出格式：
[
  {{
    "title": "示例标题",
    "summary": "示例摘要...",
    "detail": "详细信息...",
    "source_url": "",
    "is_hot": true
  }}
]

现在请根据用户需求生成 {max_topics} 条选题：
"""
    
    try:
        if backend == "openai":
            from modules.ai_writer import _call_openai
            response = _call_openai(generate_prompt, config)
        elif backend == "ollama":
            from modules.ai_writer import _call_ollama
            response = _call_ollama(generate_prompt, config)
        else:
            return None
        
        response = response.strip()
        # 提取 JSON 数组
        arr_match = re.search(r'\[.*\]', response, re.DOTALL)
        if arr_match:
            topics = json.loads(arr_match.group(0))
            if isinstance(topics, list):
                # 验证每条选题的格式
                valid_topics = []
                for t in topics:
                    if isinstance(t, dict) and 'title' in t:
                        valid_topics.append({
                            "title": t.get("title", "")[:80],
                            "summary": t.get("summary", "")[:150],
                            "detail": t.get("detail", t.get("summary", ""))[:200],
                            "source_url": t.get("source_url", ""),
                            "is_hot": t.get("is_hot", False),
                            "ai_score": 0.0,  # 后续评分
                        })
                if valid_topics:
                    print(f"   ✅ AI大模型生成 {len(valid_topics)} 条选题")
                    return valid_topics
        
        print("   ⚠️  AI大模型返回格式不正确")
        return None
    except Exception as e:
        print(f"   ⚠️  AI大模型生成选题失败：{e}")
        return None


def _ai_score_topic(topic: Dict, prompt: str, backend: str, config: dict) -> float:
    """
    使用 LLM 给选题打分（1-10 分），评估其写作价值。
    """
    title   = topic.get("title", "")
    summary = topic.get("summary", "")
    detail  = topic.get("detail", summary)

    # 构建评估提示词
    scoring_prompt = f"""你是专业的内容编辑，请根据用户的需求，对以下候选选题进行评估。

## 用户需求
{prompt}

## 候选选题
**标题：** {title}
**摘要：** {summary}
**详情：** {detail}

## 评估维度
1. **信息量**（1-3 分）：是否有新增、有价值的信息点？还是老生常谈？
2. **受众兴趣**（1-3 分）：目标读者（智能手机用户、科技爱好者）是否感兴趣？
3. **写作潜力**（1-4 分）：是否能展开成一篇有深度、有观点的文章？

请直接输出一个数字（1-10），不要加任何解释、标点、单位。
只需给出最终评分，例如：7
"""

    try:
        if backend == "openai":
            from modules.ai_writer import _call_openai
            resp = _call_openai(scoring_prompt, config)
        elif backend == "ollama":
            from modules.ai_writer import _call_ollama
            resp = _call_ollama(scoring_prompt, config)
        else:
            return 0.0  # 无 LLM，返回 0 分
        
        # 提取数字
        match = re.search(r'(\d+(?:\.\d+)?)', resp.strip())
        if match:
            score = float(match.group(1))
            # 限制在 1-10 范围内
            return max(1.0, min(10.0, score))
        return 0.0
    except Exception as e:
        print(f"   ⚠️  AI 评分失败：{e}")
        return 0.0


def ai_enhance_topics(topics: List[Dict], prompt: str, domain: str = "", max_to_score: int = 8) -> List[Dict]:
    """
    对选题列表进行 AI 增强：打分、排序、添加推荐理由。
    """
    if not topics:
        return topics

    # 检测 LLM
    backend, config = _detect_llm_backend()
    if backend == "template":
        print("   ⚠️  未检测到可用 LLM，跳过 AI 选题增强")
        return topics

    print(f"   🤖 使用 {backend} 对前 {min(len(topics), max_to_score)} 条选题进行 AI 评分...")

    # 只对前 max_to_score 条评分（避免 token 消耗）
    to_score = topics[:max_to_score]
    scored = []

    for i, topic in enumerate(to_score):
        score = _ai_score_topic(topic, prompt, backend, config)
        scored.append((topic, score))
        print(f"      {i+1}. {topic['title'][:40]}... → {score:.1f} 分")
        # 避免频率过高（如果是远程 API）
        if i < len(to_score) - 1:
            time.sleep(0.5)

    # 按分数降序排序
    scored.sort(key=lambda x: x[1], reverse=True)

    # 重新生成排序后的列表（带 AI 评分）
    enhanced = []
    for rank, (topic, score) in enumerate(scored, 1):
        topic["ai_score"] = score
        topic["rank"] = rank
        if score >= 7.0:
            topic["is_hot"] = True  # AI 推荐的热点
        enhanced.append(topic)

    # 把未评分的加在后面
    if len(topics) > max_to_score:
        for topic in topics[max_to_score:]:
            topic["ai_score"] = 0.0
            enhanced.append(topic)

    return enhanced


# ════════════════════════════════════════════════════════════
# 选出最佳选题
# ════════════════════════════════════════════════════════════

def pick_best_topic(topics: List[Dict], prefer_hot: bool = True, use_ai: bool = True) -> Optional[Dict]:
    """
    从选题列表中挑选最适合写成文章的一条。
    优先级：AI 评分 > is_hot > 原始顺序
    """
    if not topics:
        return None
    
    # 优先选择有 AI 评分且分数高的
    ai_scored = [t for t in topics if t.get("ai_score", 0) >= 1.0]
    if ai_scored and use_ai:
        ai_scored.sort(key=lambda x: x.get("ai_score", 0), reverse=True)
        return ai_scored[0]
    
    # fallback：原先的逻辑
    if prefer_hot:
        hot_topics = [t for t in topics if t.get("is_hot")]
        if hot_topics:
            return hot_topics[0]
    
    return topics[0]


def format_topics_markdown(topics: List[Dict], prompt_hint: str = "") -> str:
    """将选题列表格式化为 Markdown 字符串"""
    today = datetime.now().strftime("%Y年%m月%d日")
    lines = [f"## 📱 {today} 自动选题结果\n"]
    if prompt_hint:
        lines.append(f"> 选题方向：{prompt_hint[:80]}\n")
    lines.append("")

    for t in topics:
        rank    = t.get("rank", "")
        title   = t.get("title", "")
        summary = t.get("summary", "")
        is_hot  = "🔥" if t.get("is_hot") else ""
        url     = t.get("source_url", "")

        lines.append(f"**{rank}. {is_hot}{title}**")
        if summary:
            lines.append(f"   {summary}")
        if url:
            lines.append(f"   [来源]({url})")
        lines.append("")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# CLI 快速测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_prompt = (
        "请整理【当天手机领域最值得关注的10条动态】，"
        "重点覆盖以下方向：新机，用机，选机，AI智能化等热度较高的选题。"
        "筛选标准：优先选择具备「新增信息量」的动态。"
    )
    print("🔍 开始自动选题（手机领域）...\n")
    topics = generate_topics(
        prompt=test_prompt,
        domain="手机数码",
        max_topics=10,
        cache_hours=0,  # 测试时不走缓存
    )
    print(f"\n共获取 {len(topics)} 条选题：")
    md = format_topics_markdown(topics, prompt_hint="手机领域 新机/AI智能化")
    print(md)
    best = pick_best_topic(topics)
    if best:
        print(f"🏆 推荐写作选题：{best['title']}")
        print(f"   来源：{best.get('source_url', '')}")
