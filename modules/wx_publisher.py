"""
wx_publisher.py
微信公众号 API 对接模块

覆盖完整发布流程：
1. access_token 获取与缓存（2 小时有效期）
2. 永久素材上传（封面图）
3. 草稿创建（draft/add）
4. 提交发布（freepublish/submit）
5. 查询发布状态（freepublish/get）

文档参考：
- https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Draft_Box.html
- https://developers.weixin.qq.com/doc/offiaccount/Publish/Publish.html
"""

import os
import json
import time
import hashlib
import mimetypes
from datetime import datetime, timedelta
import requests
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List


# ────────────────────────────────────────────────────────
# 常量
# ────────────────────────────────────────────────────────
WX_API_BASE = "https://api.weixin.qq.com/cgi-bin"
TOKEN_CACHE_FILE = Path(__file__).parent.parent / ".cache" / "wx_token.json"

# 微信接口错误码
WX_SUCCESS = 0


class WeChatPublisher:
    """
    微信公众号发布客户端

    Usage:
        publisher = WeChatPublisher(app_id="...", app_secret="...")
        result = publisher.publish_article(
            title="文章标题",
            content_html="<p>正文 HTML</p>",
            cover_image_path="/path/to/cover.jpg",
            digest="文章摘要",
            author="作者名",
        )
    """

    # ══════════════════════════════════════════════════════
    # 通用：安全解析微信 API 响应
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _parse_response(resp: requests.Response, api_name: str = "") -> Dict:
        """
        安全解析微信 API 响应，处理非 JSON 的情况。

        Args:
            resp:      requests 响应对象
            api_name:  API 名称（用于错误信息）

        Returns:
            dict: 解析后的 JSON

        Raises:
            WeChatAPIError: 响应解析失败或 HTTP 错误
        """
        # 检查 HTTP 状态码
        if resp.status_code != 200:
            raise WeChatAPIError(
                f"{api_name} 请求失败 (HTTP {resp.status_code})"
            )

        # 尝试解析 JSON
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            body = resp.text[:200]
            raise WeChatAPIError(
                f"{api_name} 返回非 JSON 响应 (Content-Type: {content_type})，"
                f"前200字符: {body}"
            )

        try:
            data = resp.json()
        except Exception:
            body = resp.text[:200]
            raise WeChatAPIError(
                f"{api_name} JSON 解析失败，响应内容: {body}"
            )

        # 检查微信业务错误码
        if data.get("errcode") and data.get("errcode") != 0:
            errcode = data["errcode"]
            errmsg = data.get("errmsg", "未知错误")
            # 常见错误码映射
            err_map = {
                40001: "access_token 无效或过期",
                40002: "grant_type 不合法",
                40013: "AppID 不合法",
                41001: "缺少 access_token",
                42001: "access_token 已过期",
                45009: "API 调用频率超限",
                45064: "API 调用太频繁，请稍后再试",
                61004: "token 已过期，请重新获取",
                87009: "IP 地址不在白名单中",
                88000: "没有权限调用该接口",
                100001: "参数不合法",
                200002: "请求过于频繁",
                300001: "该公众号没有该接口的权限",
            }
            hint = err_map.get(errcode, "")
            msg = f"{errmsg}" + (f"（{hint}）" if hint else "")
            raise WeChatAPIError(
                f"{api_name} 失败 (errcode={errcode}): {msg}"
            )

        return data

    def __init__(self, app_id: str = "", app_secret: str = ""):
        """
        Args:
            app_id:     微信公众号 AppID（优先从参数读取，其次读环境变量 WX_APP_ID）
            app_secret: 微信公众号 AppSecret（优先从参数读取，其次读环境变量 WX_APP_SECRET）
        """
        self.app_id = app_id or os.environ.get("WX_APP_ID", "")
        self.app_secret = app_secret or os.environ.get("WX_APP_SECRET", "")
        self._token_cache: Optional[Dict] = None

        if not self.app_id or not self.app_secret:
            raise ValueError(
                "请提供 AppID 和 AppSecret。\n"
                "方式一：WeChatPublisher(app_id='...', app_secret='...')\n"
                "方式二：设置环境变量 WX_APP_ID 和 WX_APP_SECRET"
            )

    # ══════════════════════════════════════════════════════
    # 公开方法：完整发布流程
    # ══════════════════════════════════════════════════════

    def publish_article(
        self,
        title: str,
        content_html: str,
        cover_image_path: Optional[str] = None,
        digest: str = "",
        author: str = "",
        need_open_comment: bool = False,
        only_fans_can_comment: bool = False,
    ) -> Dict[str, Any]:
        """
        一键发布文章到微信公众号

        Args:
            title:               文章标题
            content_html:        正文 HTML（内联样式）
            cover_image_path:    封面图本地路径（可选）
            digest:              文章摘要（≤54字，不填则自动截取）
            author:              作者名
            need_open_comment:   是否开启评论
            only_fans_can_comment: 是否仅粉丝可评论

        Returns:
            dict: {
                "success": bool,
                "publish_id": str,   # 发布任务 ID
                "media_id": str,     # 草稿 media_id
                "msg": str,          # 结果消息
            }
        """
        print(f"\n📤 开始发布文章：{title}")

        # ── 步骤1：获取 access_token ─────────────────────
        token = self.get_access_token()
        print(f"   ✅ access_token 获取成功")

        # ── 步骤2：上传封面图 ────────────────────────────
        thumb_media_id = ""
        if cover_image_path and Path(cover_image_path).exists():
            thumb_media_id = self.upload_image(cover_image_path, media_type="thumb")
            print(f"   ✅ 封面图上传成功：{thumb_media_id[:20]}...")
        else:
            print(f"   ⚠️  未提供封面图，将使用默认封面")

        # ── 步骤3：自动生成摘要 ──────────────────────────
        if not digest:
            from .keyword_extractor import suggest_digest
            import re
            plain_text = re.sub(r"<[^>]+>", " ", content_html)
            digest = suggest_digest(plain_text, title=title)

        # ── 步骤4：创建草稿 ──────────────────────────────
        article = {
            "title": title,
            "author": author,
            "digest": digest,
            "content": content_html,
            "content_source_url": "",  # 原文链接（可选）
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1 if need_open_comment else 0,
            "only_fans_can_comment": 1 if only_fans_can_comment else 0,
        }

        media_id = self.create_draft(article)
        print(f"   ✅ 草稿创建成功：media_id = {media_id[:20]}...")

        # ── 步骤5：提交发布 ──────────────────────────────
        publish_id = self.submit_publish(media_id)
        print(f"   ✅ 发布提交成功：publish_id = {publish_id}")
        print(f"\n🎉 文章已提交发布！通常 1~3 分钟后在公众号可见。")

        return {
            "success": True,
            "publish_id": publish_id,
            "media_id": media_id,
            "msg": "发布成功，请在公众号后台查看审核状态",
        }

    def create_draft_only(
        self,
        title: str,
        content_html: str,
        cover_image_path: Optional[str] = None,
        digest: str = "",
        author: str = "",
    ) -> Dict[str, Any]:
        """
        仅创建草稿（不提交发布）——适合先检查再人工发布的场景

        Returns:
            dict: {"success": bool, "media_id": str, "msg": str}
        """
        print(f"\n📝 创建草稿：{title}")

        token = self.get_access_token()

        thumb_media_id = ""
        if cover_image_path and Path(cover_image_path).exists():
            thumb_media_id = self.upload_image(cover_image_path, media_type="thumb")
            print(f"   ✅ 封面图上传成功")

        if not digest:
            from .keyword_extractor import suggest_digest
            import re
            plain = re.sub(r"<[^>]+>", " ", content_html)
            digest = suggest_digest(plain, title=title)

        article = {
            "title": title,
            "author": author,
            "digest": digest,
            "content": content_html,
            "content_source_url": "",
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }

        media_id = self.create_draft(article)
        print(f"   ✅ 草稿创建成功：{media_id[:20]}...")
        print(f"   💡 请登录公众号后台审核后手动发布")

        return {
            "success": True,
            "media_id": media_id,
            "msg": "草稿已创建，可在公众号后台查看",
        }

    # ══════════════════════════════════════════════════════
    # access_token 管理
    # ══════════════════════════════════════════════════════

    def get_access_token(self) -> str:
        """
        获取 access_token（带本地文件缓存，有效期 7200 秒）

        Returns:
            str: access_token
        """
        # 检查内存缓存
        if self._token_cache:
            if time.time() < self._token_cache["expire_at"] - 60:
                return self._token_cache["token"]

        # 检查文件缓存
        cached = self._load_token_cache()
        if cached:
            self._token_cache = cached
            return cached["token"]

        # 向微信服务器请求新 token
        url = f"{WX_API_BASE}/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = self._parse_response(resp, "token")

        if "access_token" not in data:
            raise WeChatAPIError(
                f"获取 access_token 失败：{data.get('errmsg', '未知错误')} "
                f"(errcode={data.get('errcode')})"
            )

        token_info = {
            "token": data["access_token"],
            "expire_at": time.time() + data.get("expires_in", 7200),
        }
        self._token_cache = token_info
        self._save_token_cache(token_info)

        return token_info["token"]

    def _load_token_cache(self) -> Optional[Dict]:
        """从文件加载 token 缓存"""
        try:
            if TOKEN_CACHE_FILE.exists():
                with open(TOKEN_CACHE_FILE, "r") as f:
                    data = json.load(f)
                # 验证 appid 匹配且未过期
                if (data.get("app_id") == self.app_id
                        and time.time() < data.get("expire_at", 0) - 60):
                    return {"token": data["token"], "expire_at": data["expire_at"]}
        except Exception:
            pass
        return None

    def _save_token_cache(self, token_info: Dict):
        """保存 token 到文件缓存"""
        try:
            TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {
                "app_id": self.app_id,
                "token": token_info["token"],
                "expire_at": token_info["expire_at"],
            }
            with open(TOKEN_CACHE_FILE, "w") as f:
                json.dump(cache_data, f)
        except Exception:
            pass  # 缓存写失败不影响主流程

    # ══════════════════════════════════════════════════════
    # 素材上传
    # ══════════════════════════════════════════════════════

    def upload_image(self, image_path: str, media_type: str = "thumb") -> str:
        """
        上传图片到微信永久素材库

        Args:
            image_path: 本地图片路径
            media_type: 素材类型 thumb（缩略图/封面）/ image（正文图）

        Returns:
            str: media_id（永久素材 ID）
        """
        token = self.get_access_token()
        url = f"{WX_API_BASE}/material/add_material"
        params = {"access_token": token, "type": media_type}

        path = Path(image_path)
        mime_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"

        with open(path, "rb") as f:
            files = {"media": (path.name, f, mime_type)}
            resp = requests.post(url, params=params, files=files, timeout=30)

        data = self._parse_response(resp, "material/add_material")
        if "media_id" not in data:
            raise WeChatAPIError(
                f"上传图片失败：{data.get('errmsg', '未知')} "
                f"(errcode={data.get('errcode')})"
            )
        return data["media_id"]

    def upload_article_image(self, image_path: str) -> str:
        """
        上传正文图片（临时素材，3天有效）
        返回可在正文 img 标签中使用的 URL

        Returns:
            str: 图片 URL
        """
        token = self.get_access_token()
        url = f"{WX_API_BASE}/media/uploadimg"
        params = {"access_token": token}

        path = Path(image_path)
        with open(path, "rb") as f:
            files = {"media": (path.name, f, "image/jpeg")}
            resp = requests.post(url, params=params, files=files, timeout=30)

        data = self._parse_response(resp, "media/uploadimg")
        if "url" not in data:
            raise WeChatAPIError(
                f"上传正文图片失败：{data.get('errmsg', '未知')} "
                f"(errcode={data.get('errcode')})"
            )
        return data["url"]

    # ══════════════════════════════════════════════════════
    # 草稿操作
    # ══════════════════════════════════════════════════════

    def create_draft(self, article: Dict[str, Any]) -> str:
        """
        在微信草稿箱创建文章草稿

        Args:
            article: 文章信息字典，包含 title/author/content/thumb_media_id 等

        Returns:
            str: media_id（草稿 ID）
        """
        token = self.get_access_token()
        url = f"{WX_API_BASE}/draft/add"
        params = {"access_token": token}

        payload = {"articles": [article]}
        resp = requests.post(
            url, params=params,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=15,
        )
        data = self._parse_response(resp, "draft/add")

        if data.get("errcode", 0) != WX_SUCCESS and "media_id" not in data:
            raise WeChatAPIError(
                f"创建草稿失败：{data.get('errmsg', '未知')} "
                f"(errcode={data.get('errcode')})"
            )
        return data["media_id"]

    def get_draft_list(self, offset: int = 0, count: int = 20) -> Dict:
        """获取草稿列表"""
        token = self.get_access_token()
        url = f"{WX_API_BASE}/draft/batchget"
        params = {"access_token": token}
        payload = {"offset": offset, "count": count, "no_content": 1}
        resp = requests.post(url, params=params, json=payload, timeout=10)
        return self._parse_response(resp, "draft/batchget")

    def delete_draft(self, media_id: str) -> bool:
        """删除草稿"""
        token = self.get_access_token()
        url = f"{WX_API_BASE}/draft/delete"
        params = {"access_token": token}
        resp = requests.post(url, params=params, json={"media_id": media_id}, timeout=10)
        data = self._parse_response(resp, "draft/delete")
        return data.get("errcode", -1) == WX_SUCCESS

    # ══════════════════════════════════════════════════════
    # 发布操作
    # ══════════════════════════════════════════════════════

    def submit_publish(self, media_id: str) -> str:
        """
        提交草稿发布

        Args:
            media_id: 草稿 media_id

        Returns:
            str: publish_id（发布任务 ID）
        """
        token = self.get_access_token()
        url = f"{WX_API_BASE}/freepublish/submit"
        params = {"access_token": token}
        payload = {"media_id": media_id}

        resp = requests.post(url, params=params, json=payload, timeout=15)
        data = self._parse_response(resp, "freepublish/submit")

        if data.get("errcode", 0) != WX_SUCCESS and "publish_id" not in data:
            raise WeChatAPIError(
                f"提交发布失败：{data.get('errmsg', '未知')} "
                f"(errcode={data.get('errcode')})"
            )
        return str(data.get("publish_id", ""))

    def get_publish_status(self, publish_id: str) -> Dict:
        """
        查询发布状态

        Returns:
            dict: {
                "status": int,   # 0=成功 1=发布中 2=失败
                "fail_idx": list,
                "article_id": str,  # 成功后的文章 ID
            }
        """
        token = self.get_access_token()
        url = f"{WX_API_BASE}/freepublish/get"
        params = {"access_token": token}
        payload = {"publish_id": publish_id}

        resp = requests.post(url, params=params, json=payload, timeout=10)
        data = self._parse_response(resp, "freepublish/get")

        publish_info = data.get("publish_info", {})
        return {
            "raw": data,
            "status": publish_info.get("status", -1),
            "fail_idx": publish_info.get("fail_idx", []),
            "article_id": publish_info.get("article_id", ""),
        }

    def wait_for_publish(
        self,
        publish_id: str,
        max_wait: int = 120,
        interval: int = 5,
    ) -> Dict:
        """
        轮询等待发布完成

        Args:
            publish_id: 发布任务 ID
            max_wait:   最大等待秒数
            interval:   轮询间隔秒数

        Returns:
            dict: 最终发布状态
        """
        start = time.time()
        while time.time() - start < max_wait:
            status = self.get_publish_status(publish_id)
            s = status["status"]

            if s == 0:
                print(f"   🎉 发布成功！文章 ID：{status['article_id']}")
                return status
            elif s == 2:
                print(f"   ❌ 发布失败：{status['raw']}")
                return status
            else:
                elapsed = int(time.time() - start)
                print(f"   ⏳ 发布中...（已等待 {elapsed}s）")
                time.sleep(interval)

        print(f"   ⚠️  等待超时（{max_wait}s），请手动检查发布状态")
        return {"status": -1, "msg": "timeout"}

    # ══════════════════════════════════════════════════════
    # 文章数据统计（爆款分析）
    # ══════════════════════════════════════════════════════

    def get_published_articles(self, offset: int = 0, count: int = 20) -> Dict:
        """
        获取已发布文章列表（freepublish/getarticle）

        Args:
            offset: 起始偏移
            count: 数量（最大 20）

        Returns:
            dict: API 原始返回
        """
        token = self.get_access_token()
        url = f"{WX_API_BASE}/freepublish/getarticle"
        params = {"access_token": token}
        payload = {"offset": offset, "count": min(count, 20), "no_content": 1}
        resp = requests.post(url, params=params, json=payload, timeout=15)
        data = self._parse_response(resp, "freepublish/getarticle")
        return data

    def get_article_total_stats(self, begin_date: str, end_date: str) -> Dict:
        """
        获取图文群发总数据（datacube/getarticletotal）

        Args:
            begin_date: 起始日期，格式 "2026-04-01"
            end_date:   结束日期，格式 "2026-04-18"

        Returns:
            dict: API 原始返回，包含 list 字段
        """
        token = self.get_access_token()
        url = f"{WX_API_BASE}/datacube/getarticletotal"
        params = {"access_token": token}
        payload = {
            "begin_date": begin_date,
            "end_date": end_date,
        }
        resp = requests.post(url, params=params, json=payload, timeout=15)
        data = self._parse_response(resp, "getarticletotal")
        return data

    def get_user_read_summary(self, begin_date: str, end_date: str) -> Dict:
        """
        获取图文阅读概况（datacube/getuserread）

        Args:
            begin_date: 起始日期
            end_date:   结束日期

        Returns:
            dict: API 原始返回
        """
        token = self.get_access_token()
        url = f"{WX_API_BASE}/datacube/getuserread"
        params = {"access_token": token}
        payload = {
            "begin_date": begin_date,
            "end_date": end_date,
        }
        resp = requests.post(url, params=params, json=payload, timeout=15)
        data = self._parse_response(resp, "getuserread")
        return data

    def get_user_share_summary(self, begin_date: str, end_date: str) -> Dict:
        """
        获取图文转发概况（datacube/getusershare）

        Args:
            begin_date: 起始日期
            end_date:   结束日期

        Returns:
            dict: API 原始返回
        """
        token = self.get_access_token()
        url = f"{WX_API_BASE}/datacube/getusershare"
        params = {"access_token": token}
        payload = {
            "begin_date": begin_date,
            "end_date": end_date,
        }
        resp = requests.post(url, params=params, json=payload, timeout=15)
        data = self._parse_response(resp, "getusershare")
        return data

    def fetch_viral_data(self, days: int = 7) -> Dict[str, Any]:
        """
        一站式获取爆款分析数据：文章列表 + 统计数据，按热度排序

        Args:
            days: 查询最近几天的数据

        Returns:
            dict: {
                "success": bool,
                "articles": [  # 按热度降序
                    {
                        "title": str,
                        "aid": str,
                        "publish_time": str,
                        "read_count": int,      # 累计阅读
                        "like_count": int,       # 点赞+在看
                        "share_count": int,      # 转发次数
                        "share_user_count": int, # 转发人数
                        "collect_count": int,    # 收藏
                        "comment_count": int,    # 评论（如有）
                        "heat_score": float,     # 热度评分
                    }
                ],
                "total": int,
                "date_range": [str, str],
                "error": str  # 错误信息
            }
        """
        today = datetime.now()
        end_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        begin_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")

        result = {
            "success": True,
            "articles": [],
            "total": 0,
            "date_range": [begin_date, end_date],
        }

        try:
            # 1. 获取文章总统计数据
            stats_data = self.get_article_total_stats(begin_date, end_date)

            if "list" not in stats_data:
                errcode = stats_data.get("errcode", 0)
                errmsg = stats_data.get("errmsg", "未知错误")
                return {
                    **result,
                    "success": False,
                    "error": f"获取统计数据失败: {errmsg} (errcode={errcode})",
                }

            # 2. 获取转发数据（share 数据在 getarticletotal 中可能不全）
            share_data = self.get_user_share_summary(begin_date, end_date)
            share_map = {}  # title -> share_info
            if "list" in share_data:
                for item in share_data["list"]:
                    for stat in item.get("data", []):
                        title = stat.get("title", "")
                        if title:
                            if title not in share_map:
                                share_map[title] = {"share_count": 0, "share_user_count": 0}
                            share_map[title]["share_count"] += stat.get("share_count", 0) or 0
                            share_map[title]["share_user_count"] += stat.get("share_user_count", 0) or 0

            # 3. 构建文章统计列表
            article_map = {}  # aid -> 统计数据

            for date_item in stats_data["list"]:
                for stat in date_item.get("data", []):
                    aid = stat.get("aid", "")
                    if not aid:
                        continue

                    if aid not in article_map:
                        article_map[aid] = {
                            "title": stat.get("title", "无标题"),
                            "aid": aid,
                            "publish_time": stat.get("date", ""),
                            "read_count": 0,
                            "like_count": 0,
                            "share_count": 0,
                            "share_user_count": 0,
                            "collect_count": 0,
                            "comment_count": 0,
                        }

                    item = article_map[aid]
                    item["read_count"] += stat.get("read_count", 0) or 0
                    item["like_count"] += stat.get("like_count", 0) or 0
                    item["like_count"] += stat.get("like_user_count", 0) or 0  # "在看"也算
                    item["collect_count"] += stat.get("collect_count", 0) or 0

                    # 从 share_map 补充转发数据
                    title = stat.get("title", "")
                    if title in share_map:
                        item["share_count"] = share_map[title]["share_count"]
                        item["share_user_count"] = share_map[title]["share_user_count"]

            # 4. 计算热度评分并排序
            for aid, item in article_map.items():
                read = item["read_count"]
                like = item["like_count"]
                share = item["share_count"] + item["share_user_count"]
                collect = item["collect_count"]
                # 热度算法：阅读权重1 + 点赞权重5 + 转发权重10 + 收藏权重3
                item["heat_score"] = round(read * 1 + like * 5 + share * 10 + collect * 3, 1)

            articles = sorted(article_map.values(), key=lambda x: x["heat_score"], reverse=True)

            return {
                **result,
                "articles": articles,
                "total": len(articles),
            }

        except Exception as e:
            return {
                **result,
                "success": False,
                "error": f"获取爆款数据异常: {str(e)}",
            }


# ────────────────────────────────────────────────────────
# 异常类
# ────────────────────────────────────────────────────────

class WeChatAPIError(Exception):
    """微信 API 调用异常"""
    pass


# ────────────────────────────────────────────────────────
# CLI 测试（沙盒模式，不实际发布）
# ────────────────────────────────────────────────────────

def _demo_dry_run():
    """演示模式：打印 API 调用流程，不实际发送请求"""
    print("=" * 55)
    print("🔌 微信公众号 API 对接模块 - 演示模式")
    print("=" * 55)

    print("""
📋 完整发布流程：

  1. get_access_token()
     → GET https://api.weixin.qq.com/cgi-bin/token
     → 缓存到 .cache/wx_token.json（2小时有效）

  2. upload_image(cover_path, media_type="thumb")
     → POST /material/add_material?type=thumb
     → 返回 thumb_media_id

  3. create_draft(article_dict)
     → POST /draft/add
     → 返回 media_id

  4. submit_publish(media_id)
     → POST /freepublish/submit
     → 返回 publish_id

  5. get_publish_status(publish_id)  [可选轮询]
     → POST /freepublish/get
     → status: 0=成功 1=进行中 2=失败

📝 配置方式：
   export WX_APP_ID="your_appid"
   export WX_APP_SECRET="your_appsecret"

   或在代码中：
   publisher = WeChatPublisher(app_id="...", app_secret="...")
""")

    print("✅ 模块加载成功！配置好 AppID/AppSecret 即可使用。")


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        # 实际测试：python wx_publisher.py <appid> <appsecret>
        publisher = WeChatPublisher(app_id=sys.argv[1], app_secret=sys.argv[2])
        try:
            token = publisher.get_access_token()
            print(f"✅ access_token 获取成功（前20位）：{token[:20]}...")
        except WeChatAPIError as e:
            print(f"❌ {e}")
    else:
        _demo_dry_run()
