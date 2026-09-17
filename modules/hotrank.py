"""
modules/hotrank.py
每日热搜榜数据抓取模块

支持平台：
  哔哩哔哩、微博、知乎、百度、抖音、豆瓣、IT之家、少数派、
  澎湃新闻、今日头条、36氪、稀土掘金、腾讯新闻、网易新闻
"""

import re
import time
import json
import random
import requests
from typing import List, Dict, Optional

# ── 超时与重试 ────────────────────────────────────────────
TIMEOUT = 10

def _ua():
    return random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ])

def _get(url, headers=None, params=None, referer=None) -> Optional[requests.Response]:
    h = {"User-Agent": _ua(), "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer:
        h["Referer"] = referer
    if headers:
        h.update(headers)
    try:
        resp = requests.get(url, headers=h, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp
    except Exception as e:
        print(f"   [hotrank] 请求失败 {url}: {e}")
        return None


# ════════════════════════════════════════════════════════════
# 各平台抓取函数
# ════════════════════════════════════════════════════════════

def fetch_weibo() -> List[Dict]:
    """微博热搜 - 使用微博国际版接口"""
    url = "https://weibo.com/ajax/statuses/hot_band"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://weibo.com/hot/search",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    resp = _get(url, headers=headers)
    if not resp:
        return []
    
    try:
        data = resp.json()
        items = data.get("data", {}).get("band_list", [])
        result = []
        for i, item in enumerate(items[:20]):
            title = item.get("word", "").strip()
            hot = item.get("raw_hot", "")
            if title:
                result.append({
                    "rank": i + 1,
                    "title": title[:80],
                    "hot": str(hot) if hot else "",
                    "url": f"https://s.weibo.com/weibo?q={requests.utils.quote(title)}",
                })
        return result
    except Exception as e:
        print(f"   [hotrank/微博] 解析失败: {e}")
        return []


def fetch_zhihu() -> List[Dict]:
    """知乎热榜 - 使用 zhihu_daily 接口避免认证"""
    url = "https://news-at.zhihu.com/api/4/news/hot"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    }
    resp = _get(url, headers=headers)
    if not resp:
        return []
    try:
        data = resp.json()
        items = data.get("recent", [])
        result = []
        for i, item in enumerate(items[:20]):
            title = item.get("title", "").strip()
            url_path = item.get("url", "")
            # url 是 API 端点如 http://news-at.zhihu.com/api/2/news/9788907
            # 提取文章ID拼接成网页链接
            id_match = re.search(r'/news/(\d+)', url_path)
            if id_match:
                article_url = f"https://daily.zhihu.com/story/{id_match.group(1)}"
            else:
                article_url = url_path
            if title:
                result.append({
                    "rank": i + 1,
                    "title": title,
                    "hot": "",
                    "url": article_url,
                })
        return result
    except Exception as e:
        print(f"   [hotrank/知乎] 解析失败: {e}")
        return []


def fetch_baidu() -> List[Dict]:
    """百度热搜"""
    url = "https://top.baidu.com/board?tab=realtime"
    resp = _get(url)
    if not resp:
        return []
    try:
        # 从 HTML 中提取 JSON 数据
        m = re.search(r'<!--s-data:(.*?)-->', resp.text, re.DOTALL)
        if not m:
            return []
        raw = m.group(1).strip()
        data = json.loads(raw)
        cards = data.get("data", {}).get("cards", [])
        result = []
        rank = 1
        for card in cards:
            for item in card.get("content", []):
                title = item.get("word", "").strip()
                hot = item.get("hotScore", "")
                url_path = item.get("url", "")
                if title:
                    result.append({
                        "rank": rank,
                        "title": title,
                        "hot": str(hot) if hot else "",
                        "url": url_path or f"https://www.baidu.com/s?wd={requests.utils.quote(title)}",
                    })
                    rank += 1
                    if rank > 20:
                        break
            if rank > 20:
                break
        return result
    except Exception as e:
        print(f"   [hotrank/百度] 解析失败: {e}")
        return []


def fetch_bilibili() -> List[Dict]:
    """哔哩哔哩热门视频"""
    url = "https://api.bilibili.com/x/web-interface/search/square?limit=20&platform=web"
    resp = _get(url, headers={"Accept": "application/json"}, referer="https://www.bilibili.com/")
    if not resp:
        return []
    try:
        data = resp.json()
        items = data.get("data", {}).get("trending", {}).get("list", [])
        result = []
        for i, item in enumerate(items[:20]):
            title = item.get("show_name") or item.get("keyword", "")
            title = title.strip()
            if title:
                result.append({
                    "rank": i + 1,
                    "title": title,
                    "hot": str(item.get("heat", "")),
                    "url": f"https://search.bilibili.com/all?keyword={requests.utils.quote(title)}",
                })
        return result
    except Exception as e:
        print(f"   [hotrank/哔哩哔哩] 解析失败: {e}")
        return []


def fetch_douban() -> List[Dict]:
    """豆瓣热门话题 - 从小组探索页面解析"""
    url = "https://www.douban.com/group/explore"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        result = []
        seen = set()
        rank = 1
        
        # 匹配 h3 中的话题链接和标题
        # 格式: <h3><a href="https://www.douban.com/group/topic/xxx">标题</a></h3>
        pattern = r'<h3>\s*<a[^>]*href="(https://www\.douban\.com/group/topic/(\d+)[^"]*)"[^>]*>(.*?)</a>\s*</h3>'
        matches = re.findall(pattern, resp.text, re.DOTALL)
        
        for link, topic_id, title_html in matches:
            if rank > 20:
                break
            # 清理标题中的HTML标签
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            if title and title not in seen and len(title) > 5 and len(title) < 100:
                seen.add(title)
                result.append({
                    "rank": rank,
                    "title": title[:80],
                    "hot": "",
                    "url": link,
                })
                rank += 1
        return result
    except Exception as e:
        print(f"   [hotrank/豆瓣] 解析失败: {e}")
        return []


def fetch_ithome() -> List[Dict]:
    """IT之家热榜 - 使用API接口"""
    url = "https://api.ithome.com/json/newslist/news"
    params = {
        "r": "0",
        "page": 1,
        "count": 20,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.ithome.com/",
    }
    resp = _get(url, params=params, headers=headers)
    if not resp:
        return []
    try:
        data = resp.json()
        items = data.get("newslist", [])
        result = []
        rank = 1
        for item in items[:20]:
            title = item.get("title", "").strip()
            news_id = item.get("newsid", "")
            # 优先使用API返回的url字段（格式如 /0/939/246.htm）
            item_url = item.get("url", "")
            if item_url and item_url.startswith("/"):
                article_url = f"https://www.ithome.com{item_url}"
            elif item_url and item_url.startswith("http"):
                article_url = item_url
            else:
                # 降级：从newsid手动拼接
                article_url = f"https://www.ithome.com/0/{news_id}.htm" if news_id else "https://www.ithome.com/"
            if title:
                result.append({
                    "rank": rank,
                    "title": title[:80],
                    "hot": "",
                    "url": article_url,
                })
                rank += 1
        return result
    except Exception as e:
        print(f"   [hotrank/IT之家] 解析失败: {e}")
        return []


def fetch_sspai() -> List[Dict]:
    """少数派热门 - 从首页HTML解析文章卡片"""
    url = "https://sspai.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        result = []
        seen = set()
        rank = 1
        # 匹配文章卡片：标题在 <a> 内的 <span> 文本中
        cards = re.findall(
            r'<a[^>]*href="/post/(\d+)"[^>]*>(.*?)</a>',
            resp.text, re.DOTALL
        )
        for article_id, card_content in cards:
            if rank > 20:
                break
            # 从span标签中提取标题文本
            title = ""
            # 优先查找包含标题的span
            spans = re.findall(r'<span[^>]*>(.*?)</span>', card_content, re.DOTALL)
            for span_text in spans:
                text = re.sub(r'<[^>]+>', '', span_text).strip()
                # 标题通常较长，跳过日期等短文本
                if len(text) > 8 and len(text) < 100:
                    title = text
                    break
            # 降级：直接清理所有HTML标签取文本
            if not title:
                text = re.sub(r'<[^>]+>', '', card_content).strip()
                if len(text) > 8 and len(text) < 100:
                    title = text
            if title and title not in seen:
                seen.add(title)
                result.append({
                    "rank": rank,
                    "title": title[:80],
                    "hot": "",
                    "url": f"https://sspai.com/post/{article_id}",
                })
                rank += 1
        return result
    except Exception as e:
        print(f"   [hotrank/少数派] 解析失败: {e}")
        return []


def fetch_pengpai() -> List[Dict]:
    """澎湃新闻热榜 - 从首页HTML解析"""
    url = "https://www.thepaper.cn/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        # 匹配新闻ID
        news_ids = re.findall(r'newsDetail_forward_(\d+)', resp.text)
        result = []
        seen = set()
        rank = 1
        for nid in news_ids:
            if nid in seen or rank > 20:
                continue
            seen.add(nid)
            # 在附近查找标题
            # 找到这个ID在文本中的位置
            pos = resp.text.find(f'newsDetail_forward_{nid}')
            if pos > 0:
                # 在该位置前后500字符内查找标题
                context = resp.text[pos:pos+800]
                # 尝试多种标题模式
                title_match = re.search(r'<h2[^>]*>(.*?)</h2>', context, re.DOTALL)
                if not title_match:
                    title_match = re.search(r'title["\']?\s*[:=]\s*["\']([^"\']+)["\']', context)
                if not title_match:
                    title_match = re.search(r'>([^<]{10,60})<', context)
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                    title = re.sub(r'\s+', ' ', title)
                    if title and len(title) > 5 and len(title) < 100:
                        result.append({
                            "rank": rank,
                            "title": title[:80],
                            "hot": "",
                            "url": f"https://www.thepaper.cn/newsDetail_forward_{nid}",
                        })
                        rank += 1
        return result
    except Exception as e:
        print(f"   [hotrank/澎湃] 解析失败: {e}")
        return []


def fetch_toutiao() -> List[Dict]:
    """今日头条热榜"""
    url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
    resp = _get(url, headers={"Accept": "application/json"}, referer="https://www.toutiao.com/")
    if not resp:
        return []
    try:
        data = resp.json()
        items = data.get("data", [])
        result = []
        for i, item in enumerate(items[:20]):
            title = item.get("Title", "").strip()
            hot = item.get("HotValue", "")
            link = item.get("Url", "") or ""
            if title:
                result.append({
                    "rank": i + 1,
                    "title": title[:80],
                    "hot": str(hot) if hot else "",
                    "url": link,
                })
        return result
    except Exception as e:
        print(f"   [hotrank/头条] 解析失败: {e}")
        return []


def fetch_36kr() -> List[Dict]:
    """36氪热门文章"""
    url = "https://gateway.36kr.com/api/mis/nav/home/nav/rank/hot"
    payload = {"partner_id": "wap", "param": {"siteId": 1, "platformId": 2}}
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"User-Agent": _ua(), "Accept": "application/json", "Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("hotRankList", [])
        result = []
        for i, item in enumerate(items[:20]):
            title = item.get("templateMaterial", {}).get("widgetTitle", "").strip()
            item_id = item.get("itemId", "")
            if title:
                result.append({
                    "rank": i + 1,
                    "title": title[:80],
                    "hot": "",
                    "url": f"https://36kr.com/p/{item_id}" if item_id else "https://36kr.com/",
                })
        return result
    except Exception as e:
        print(f"   [hotrank/36氪] 解析失败: {e}")
        return []


def fetch_juejin() -> List[Dict]:
    """稀土掘金热门"""
    url = "https://api.juejin.cn/recommend_api/v1/article/recommend_cate_feed"
    payload = {"id_type": 2, "sort_type": 200, "cate_id": "6809637767543259144", "cursor": "0", "limit": 20}
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"User-Agent": _ua(), "Accept": "application/json", "Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])
        result = []
        for i, item in enumerate(items[:20]):
            article = item.get("article_info", {})
            title = article.get("title", "").strip()
            article_id = article.get("article_id", "")
            view_count = article.get("view_count", "")
            if title:
                result.append({
                    "rank": i + 1,
                    "title": title[:80],
                    "hot": f"{view_count} 浏览" if view_count else "",
                    "url": f"https://juejin.cn/post/{article_id}" if article_id else "https://juejin.cn/",
                })
        return result
    except Exception as e:
        print(f"   [hotrank/掘金] 解析失败: {e}")
        return []


def fetch_tencent_news() -> List[Dict]:
    """腾讯新闻热点 - 使用新接口"""
    url = "https://r.inews.qq.com/gw/event/hot_ranking_list"
    params = {
        "page_size": 20,
        "offset": 0,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        "Referer": "https://news.qq.com/",
    }
    resp = _get(url, params=params, headers=headers)
    if not resp:
        return []
    try:
        data = resp.json()
        # 新数据结构: idlist[0].newslist
        idlist = data.get("idlist", [])
        items = idlist[0].get("newslist", []) if idlist else []
        result = []
        rank = 1
        for item in items[:20]:
            title = item.get("title", "").strip()
            url_path = item.get("url", "")
            # 跳过提示性条目
            if title and "腾讯新闻用户最关注" not in title:
                result.append({
                    "rank": rank,
                    "title": title[:80],
                    "hot": "",
                    "url": url_path,
                })
                rank += 1
        return result
    except Exception as e:
        print(f"   [hotrank/腾讯新闻] 解析失败: {e}")
        return []


def fetch_netease_news() -> List[Dict]:
    """网易新闻热门"""
    url = "https://www.163.com/special/0077jt/newsrank.html"
    resp = _get(url, referer="https://www.163.com/")
    if not resp:
        return []
    try:
        # 提取数据
        m = re.search(r'data\s*=\s*(\[.*?\]);', resp.text, re.DOTALL)
        if m:
            items = json.loads(m.group(1))
            result = []
            for i, item in enumerate(items[:20]):
                title = item.get("title", "").strip()
                link = item.get("docurl", "") or item.get("url", "")
                if title:
                    result.append({
                        "rank": i + 1,
                        "title": title[:80],
                        "hot": "",
                        "url": link,
                    })
            return result
        # 备用：从HTML解析
        blocks = re.findall(
            r'<a[^>]*href="(https://[^"]*163\.com[^"]*)"[^>]*>(.*?)</a>',
            resp.text, re.DOTALL
        )
        result = []
        seen = set()
        rank = 1
        for link, raw_title in blocks:
            title = re.sub(r'<[^>]+>', '', raw_title).strip()
            if title and len(title) > 5 and title not in seen:
                seen.add(title)
                result.append({"rank": rank, "title": title[:80], "hot": "", "url": link})
                rank += 1
                if rank > 20:
                    break
        return result
    except Exception as e:
        print(f"   [hotrank/网易] 解析失败: {e}")
        return []


def fetch_douyin() -> List[Dict]:
    """抖音热榜（通过公开接口）"""
    url = "https://www.douyin.com/aweme/v1/web/hot/search/list/"
    params = {
        "device_platform": "webapp",
        "aid": "6383",
        "hot_search_type": 0,
    }
    resp = _get(url, params=params, headers={"Accept": "application/json"}, referer="https://www.douyin.com/")
    if not resp:
        return []
    try:
        data = resp.json()
        items = data.get("data", {}).get("word_list", [])
        result = []
        for i, item in enumerate(items[:20]):
            title = item.get("word", "").strip()
            hot = item.get("hot_value", "")
            if title:
                result.append({
                    "rank": i + 1,
                    "title": title[:80],
                    "hot": str(hot) if hot else "",
                    "url": f"https://www.douyin.com/search/{requests.utils.quote(title)}",
                })
        return result
    except Exception as e:
        print(f"   [hotrank/抖音] 解析失败: {e}")
        return []


# ════════════════════════════════════════════════════════════
# 平台注册表
# ════════════════════════════════════════════════════════════

PLATFORMS = [
    {"id": "weibo",        "name": "微博",     "icon": "🔥", "fetch": fetch_weibo},
    {"id": "baidu",        "name": "百度",     "icon": "🔍", "fetch": fetch_baidu},
    {"id": "toutiao",      "name": "今日头条", "icon": "📰", "fetch": fetch_toutiao},
    {"id": "bilibili",     "name": "哔哩哔哩", "icon": "📺", "fetch": fetch_bilibili},
    {"id": "zhihu",        "name": "知乎",     "icon": "💡", "fetch": fetch_zhihu},
    {"id": "douyin",       "name": "抖音",     "icon": "🎵", "fetch": fetch_douyin},
    {"id": "tencent_news", "name": "腾讯新闻", "icon": "📡", "fetch": fetch_tencent_news},
    {"id": "netease_news", "name": "网易新闻", "icon": "📣", "fetch": fetch_netease_news},
    {"id": "pengpai",      "name": "澎湃新闻", "icon": "🌊", "fetch": fetch_pengpai},
    {"id": "36kr",         "name": "36氪",     "icon": "💼", "fetch": fetch_36kr},
    {"id": "juejin",       "name": "稀土掘金", "icon": "⛏️", "fetch": fetch_juejin},
    {"id": "ithome",       "name": "IT之家",   "icon": "💻", "fetch": fetch_ithome},
    {"id": "sspai",        "name": "少数派",   "icon": "✨", "fetch": fetch_sspai},
    {"id": "douban",       "name": "豆瓣",     "icon": "📚", "fetch": fetch_douban},
]

PLATFORM_MAP = {p["id"]: p for p in PLATFORMS}


def get_hotrank(platform_id: str) -> Dict:
    """
    获取指定平台热搜榜。
    返回 {"ok": True/False, "platform": {...}, "items": [...], "updated_at": "..."}
    """
    platform = PLATFORM_MAP.get(platform_id)
    if not platform:
        return {"ok": False, "error": f"不支持的平台: {platform_id}"}

    print(f"   [hotrank] 抓取 {platform['name']} 热榜...")
    items = platform["fetch"]()

    from datetime import datetime
    return {
        "ok": True,
        "platform": {"id": platform["id"], "name": platform["name"], "icon": platform["icon"]},
        "items": items,
        "count": len(items),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_all_hotrankings() -> List[Dict]:
    """并发获取所有平台热榜"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(get_hotrank, p["id"]): p["id"] for p in PLATFORMS}
        for future in as_completed(futures):
            results.append(future.result())

    # 按 PLATFORMS 顺序排序
    order = [p["id"] for p in PLATFORMS]
    results.sort(key=lambda x: order.index(x.get("platform", {}).get("id", "")) if x.get("platform") else 999)
    return results
