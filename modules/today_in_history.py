"""
modules/today_in_history.py
历史上的今天数据抓取模块
"""

import re
import json
import random
import requests
from datetime import datetime
from typing import List, Dict, Optional

TIMEOUT = 10

def _ua():
    return random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ])

def _get(url, headers=None) -> Optional[requests.Response]:
    h = {"User-Agent": _ua(), "Accept-Language": "zh-CN,zh;q=0.9"}
    if headers:
        h.update(headers)
    try:
        resp = requests.get(url, headers=h, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp
    except Exception as e:
        print(f"   [today_in_history] 请求失败 {url}: {e}")
        return None


def fetch_from_baidu() -> List[Dict]:
    """百度历史上的今天"""
    today = datetime.now()
    month = today.month
    day = today.day
    
    url = f"https://baike.baidu.com/cms/home/eventsOnHistory/{month:02d}.json"
    resp = _get(url, headers={"Referer": "https://baike.baidu.com/"})
    if not resp:
        return []
    
    try:
        data = resp.json()
        # 数据结构: {"04": {"0415": [...], "0416": [...]}}
        month_key = f"{month:02d}"
        day_key = f"{month:02d}{day:02d}"
        
        if month_key not in data:
            return []
        
        month_data = data[month_key]
        if day_key not in month_data:
            return []
        
        events = []
        for item in month_data[day_key]:
            year = str(item.get("year", ""))
            title = re.sub(r'<[^>]+>', '', item.get("title", ""))
            desc = re.sub(r'<[^>]+>', '', item.get("desc", ""))
            
            events.append({
                "year": year,
                "title": title,
                "desc": desc,
                "type": _classify_event(title + desc),
            })
        return events
    except Exception as e:
        print(f"   [today_in_history] 百度解析失败: {e}")
        return []


def _classify_event(text: str) -> str:
    """分类事件类型"""
    text = text.lower()
    categories = {
        "出生": ["出生", "诞辰", "诞生"],
        "逝世": ["去世", "逝世", "病逝", "遇难", "牺牲"],
        "战争": ["战争", "战役", "战斗", "入侵", "起义", "革命"],
        "政治": ["建国", "独立", "统一", "条约", "选举", "总统", "主席"],
        "科技": ["发明", "发现", "卫星", "航天", "火箭", "飞船", "计算机"],
        "文化": ["出版", "上映", "发行", "小说", "电影", "音乐", "歌曲"],
        "体育": ["奥运会", "世界杯", "冠军", "夺冠", "金牌", "比赛"],
        "灾难": ["地震", "海啸", "洪水", "火灾", "爆炸", "空难", "事故"],
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                return category
    return "其他"


def get_today_in_history() -> Dict:
    """获取历史上的今天数据"""
    today = datetime.now()
    date_str = f"{today.month}月{today.day}日"
    
    events = fetch_from_baidu()
    
    # 按年份排序（新到旧）
    def _year_key(e):
        try:
            year = e.get("year", "0")
            if "前" in year or "BC" in year.upper():
                return -int(re.sub(r"[^\d]", "", year)) if re.sub(r"[^\d]", "", year) else 0
            return int(re.sub(r"[^\d]", "", year)) if re.sub(r"[^\d]", "", year) else 0
        except:
            return 0
    
    events.sort(key=_year_key, reverse=True)
    
    # 去重
    seen = set()
    unique_events = []
    for e in events:
        key = e.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique_events.append(e)
    
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    
    return {
        "date": date_str,
        "weekday": weekdays[today.weekday()],
        "events": unique_events[:50]
    }
