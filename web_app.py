"""
web_app.py
AI 辅助协作写作平台 — Web 可视化管理界面（Flask 后端）

启动方式：
  python web_app.py
  # 然后在浏览器打开 http://localhost:5678
"""

import os
import sys
import re
import json
import queue
import threading
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import requests

from flask import (
    Flask, request, jsonify, Response, render_template,
    send_from_directory, send_file, session, redirect,
)

# ── 项目根目录 ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

app = Flask(__name__, static_folder=str(BASE_DIR / "web_static"))
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# ── 导入用户数据库模块 ─────────────────────────────────────────
from modules.user_db import UserDB, get_current_user, get_db

# ── 历史文章模块（协同创作产出的持久化）──────────────────────────
from modules.article_history import list_articles, get_article, delete_article, save_article, list_articles_paginated

# ── 全局日志队列（SSE 用） ────────────────────────────────────
_log_queues: Dict[str, queue.Queue] = {}



# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════

def load_config() -> dict:
    """加载 AI 配置（config.json）"""
    p = BASE_DIR / "config.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(data: dict):
    """保存 config.json（仅用于 AI 配置，废弃后删除）"""
    p = BASE_DIR / "config.json"
    # 保留注释字段
    old = {}
    if p.exists():
        with open(p, encoding="utf-8") as f:
            old = json.load(f)
    old.update(data)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False, indent=2)


# ========== 账号配置 ==========
_ACCOUNTS_FILE = BASE_DIR / "accounts.json"


def get_account_config(account_id: str = None, user_id: Optional[int] = None, allow_fallback: bool = True) -> dict:
    """
    获取指定账号的完整配置（含身份 + 写作偏好）

    Args:
        account_id: 账号 ID（字符串），如 "bigdata", "tech_blog"
        user_id: 用户 ID，None 表示使用当前登录用户或 admin
        allow_fallback: 是否允许在子线程中使用 admin 用户作为兜底（子线程没有 request context）

    Returns:
        账号配置字典，含 name/author/topic_prompt/article_style/word_count/theme/writing_prompt
        如果账号不存在，返回空字典
    """
    from modules.user_db import UserDB

    # 如果没有指定 user_id，从 session 获取（仅在主线程中）
    if user_id is None and allow_fallback:
        try:
            session_id = _get_session_id()
            current_user = get_current_user(session_id)
            user_id = current_user["id"] if current_user else None
        except RuntimeError:
            # 子线程中没有 request context，使用 admin 作为兜底
            user_id = None

    with UserDB() as db:
        # 如果指定了 account_id，通过它查找账号
        if account_id:
            account = db.get_account_by_account_id(account_id)
        # 否则获取用户的默认账号
        elif user_id:
            account = db.get_user_default_account(user_id)
        elif allow_fallback:
            # 兜底：查找 admin 的默认账号
            cur = db.conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
            admin = cur.fetchone()
            if admin:
                account = db.get_user_default_account(admin[0])
            else:
                account = None
        else:
            account = None

        # 找到账号配置
        if account:
            return dict(account)

    return {}


def push_log(task_id: str, msg: str, level: str = "info"):
    """往 SSE 队列里推一条日志"""
    if task_id in _log_queues:
        _log_queues[task_id].put({"msg": msg, "level": level})


class QueueLogger:
    """重定向 print 到 SSE 队列"""
    def __init__(self, task_id: str, orig_stdout):
        self.task_id = task_id
        self.orig = orig_stdout

    def write(self, text: str):
        # Windows 控制台 GBK 编码不支持 emoji，安全回退
        try:
            self.orig.write(text)
            self.orig.flush()
        except (UnicodeEncodeError, UnicodeDecodeError):
            self.orig.write(text.encode('gbk', errors='replace').decode('gbk'))
            self.orig.flush()
        text = text.strip()
        if text:
            push_log(self.task_id, text)

    def flush(self):
        self.orig.flush()


# ════════════════════════════════════════════════════════════
# API：用户认证
# ════════════════════════════════════════════════════════════

def _get_session_id():
    """从请求中获取 session_id"""
    # 优先从 Header 读取（跨域支持）
    session_id = request.headers.get("X-Session-Id")
    if not session_id:
        # 从 Cookie 读取
        session_id = request.cookies.get("session_id")
    return session_id


@app.route("/api/user/current", methods=["GET"])
def api_get_current_user():
    """获取当前登录用户信息"""
    session_id = _get_session_id()
    user = get_current_user(session_id)

    if not user:
        return jsonify({"error": "未登录"}), 401

    # 移除敏感信息
    user.pop("password_hash", None)
    return jsonify({"success": True, "user": user})


@app.route("/api/user/change_password", methods=["POST"])
def api_change_password():
    """修改密码"""
    session_id = _get_session_id()
    user = get_current_user(session_id)

    if not user:
        return jsonify({"error": "未登录"}), 401

    data = request.get_json()
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")

    if not old_password or not new_password:
        return jsonify({"error": "请填写完整密码信息"}), 400

    if len(new_password) < 6:
        return jsonify({"error": "新密码至少需要 6 位"}), 400

    with UserDB() as db:
        # 验证旧密码
        if not db.verify_user(user["username"], old_password):
            return jsonify({"error": "当前密码不正确"}), 400

        # 更新密码
        success = db.update_password(user["id"], new_password)
        if not success:
            return jsonify({"error": "密码修改失败"}), 500

        # 删除所有会话，强制重新登录
        db.delete_all_user_sessions(user["id"])

    return jsonify({"success": True})


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    """用户注册"""
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()

    # 参数校验
    if not username or len(username) < 3:
        return jsonify({"error": "用户名至少 3 个字符"}), 400
    if not password or len(password) < 6:
        return jsonify({"error": "密码至少 6 个字符"}), 400

    with UserDB() as db:
        user_id = db.create_user(username, password, email)
        if not user_id:
            return jsonify({"error": "用户名已存在"}), 400

        # 自动登录（创建会话）
        session_id = db.create_session(user_id)

        # 返回用户信息（不含密码哈希）
        user = db.get_user_by_id(user_id)
        user.pop("password_hash", None)

        response = jsonify({
            "success": True,
            "user": user,
            "session_id": session_id,
        })

        # 设置 Cookie
        response.set_cookie(
            "session_id",
            session_id,
            max_age=24 * 3600,  # 24 小时
            httponly=True,
            samesite="Lax"
        )
        return response


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """用户登录（用户名密码）"""
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    with UserDB() as db:
        user = db.verify_user(username, password)
        if not user:
            return jsonify({"error": "用户名或密码错误"}), 401

        # 创建会话
        session_id = db.create_session(user["id"])

        response = jsonify({
            "success": True,
            "user": user,
            "session_id": session_id,
        })

        # 设置 Cookie
        response.set_cookie(
            "session_id",
            session_id,
            max_age=24 * 3600,
            httponly=True,
            samesite="Lax"
        )
        return response


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """用户登出"""
    session_id = _get_session_id()
    if session_id:
        with UserDB() as db:
            db.delete_session(session_id)

    response = jsonify({"success": True, "redirect": "/login.html"})
    response.delete_cookie("session_id")
    return response


# ════════════════════════════════════════════════════════════
# 静态首页
# ════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """首页，重定向到协作工作台"""
    return redirect("/collaborative")


@app.route("/login.html")
def login_page():
    """登录页面"""
    return send_from_directory(str(BASE_DIR / "web_static"), "login.html")


# ════════════════════════════════════════════════════════════
# 前端路由：独立页面
# ════════════════════════════════════════════════════════════

@app.route("/common.css")
def common_css():
    """提供 common.css 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "common.css")

@app.route("/collaborative.css")
def collaborative_css():
    """提供 collaborative.css 静态资源（创作工作台科技感主题）"""
    return send_from_directory(str(BASE_DIR / "web_static"), "collaborative.css")

@app.route("/common.js")
def common_js():
    """提供 common.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "common.js")


@app.route("/history.html")
def history():
    """历史文章页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "history.html")


@app.route("/settings.html")
def settings_page():
    """系统配置页面（AI 配置 + AI 模型管理）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "settings.html")


@app.route("/hotrank.html")
def hotrank_page():
    """每日热搜榜页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "hotrank.html")


@app.route("/hotrank.js")
def hotrank_js():
    """提供 hotrank.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "hotrank.js")

@app.route("/hotrank.css")
def hotrank_css():
    """提供 hotrank.css 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "hotrank.css")


# ════════════════════════════════════════════════════════════
# 历史上的今天页面路由
# ════════════════════════════════════════════════════════════

@app.route("/today_in_history.html")
def today_in_history_page():
    """历史上的今天页面"""
    session_id = _get_session_id()
    if not session_id or not get_current_user(session_id):
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "today_in_history.html")


@app.route("/today_in_history.js")
def today_in_history_js():
    """提供 today_in_history.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "today_in_history.js")


@app.route("/today_in_history.css")
def today_in_history_css():
    """提供 today_in_history.css 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "today_in_history.css")


# ════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════
# 素材库页面路由
# ════════════════════════════════════════════════════════════

@app.route("/material_library.html")
def material_library_page():
    """素材库页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "material_library.html")


@app.route("/material_library.js")
def material_library_js():
    """提供 material_library.js 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "material_library.js")


@app.route("/material_library.css")
def material_library_css():
    """提供 material_library.css 静态资源"""
    return send_from_directory(str(BASE_DIR / "web_static"), "material_library.css")


# ════════════════════════════════════════════════════════════
# AI 助手 API 路由（抽屉式面板，无独立页面）
# ════════════════════════════════════════════════════════════

@app.route("/web_static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(BASE_DIR / "web_static"), filename)


# ════════════════════════════════════════════════════════════
# API：配置管理
# ════════════════════════════════════════════════════════════

@app.route("/api/config", methods=["GET"])
def api_get_config():
    """获取 AI 配置"""
    cfg = load_config()

    # 脱敏：只返回 key 末尾 8 位
    key = cfg.get("ai_api_key", "")
    masked_key = ("*" * (len(key) - 8) + key[-8:]) if len(key) > 8 else ("*" * len(key))

    return jsonify({
        "ai_api_key":  masked_key,
        "ai_api_base": cfg.get("ai_api_base", "https://api.deepseek.com"),
        "ai_model":    cfg.get("ai_model", "deepseek-chat"),
    })


@app.route("/api/config", methods=["POST"])
def api_save_config():
    """保存 AI 配置"""
    data = request.json or {}

    main_fields = ["ai_api_base", "ai_model"]
    main_update = {k: data[k] for k in main_fields if k in data}

    # 只有新 key 非空且不是掩码才更新
    if data.get("ai_api_key") and not data["ai_api_key"].startswith("*"):
        main_update["ai_api_key"] = data["ai_api_key"]

    if main_update:
        save_config(main_update)

    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
# 写作技能管理 API
# ════════════════════════════════════════════════════════════

@app.route("/api/skills", methods=["GET"])
def api_get_skills():
    """获取当前用户的写作技能列表"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    active_only = request.args.get("active_only") == "1"
    with UserDB() as db:
        skills = db.get_user_skills(user["id"], active_only=active_only)

    return jsonify({"ok": True, "skills": skills})


@app.route("/api/skills", methods=["POST"])
def api_create_skill():
    """创建写作技能"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    name = (data.get("name") or "").strip()
    prompt_content = data.get("prompt_content", "").strip()
    description = (data.get("description") or "").strip()
    category = (data.get("category") or "通用").strip()

    if not name:
        return jsonify({"ok": False, "error": "技能名称不能为空"}), 400
    if not prompt_content:
        return jsonify({"ok": False, "error": "技能提示词不能为空"}), 400

    with UserDB() as db:
        new_id = db.create_skill(user["id"], name, prompt_content, description, category)

    if new_id:
        return jsonify({"ok": True, "id": new_id})
    else:
        return jsonify({"ok": False, "error": "创建失败"}), 500


@app.route("/api/skills/<int:skill_id>", methods=["PUT"])
def api_update_skill(skill_id: int):
    """更新写作技能"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    with UserDB() as db:
        result = db.update_skill(
            skill_id, user["id"],
            name=data.get("name"),
            prompt_content=data.get("prompt_content"),
            description=data.get("description"),
            category=data.get("category"),
            is_active=data.get("is_active"),
        )

    if result:
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "更新失败"}), 400


@app.route("/api/skills/<int:skill_id>", methods=["DELETE"])
def api_delete_skill(skill_id: int):
    """删除写作技能"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        result = db.delete_skill(skill_id, user["id"])

    if result:
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "删除失败"}), 400


@app.route("/api/articles/dedup", methods=["GET"])
def api_get_articles_for_dedup():
    """获取历史文章标题列表（用于写稿前去重）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        articles = db.get_articles_for_dedup(user["id"], limit=500)

    return jsonify({"articles": articles})


# ════════════════════════════════════════════════════════════
# API：领域分类管理
# ════════════════════════════════════════════════════════════

@app.route("/api/domains", methods=["GET"])
def api_get_domains():
    """获取用户的所有领域分类（含系统默认）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    from modules.user_db import init_system_domains
    init_system_domains(user["id"])

    with UserDB() as db:
        domains = db.get_user_domains(user["id"])
        return jsonify({"ok": True, "domains": domains})


@app.route("/api/domains", methods=["POST"])
def api_create_domain():
    """创建新领域分类"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    ref_websites = data.get("ref_websites", [])
    if not isinstance(ref_websites, list):
        ref_websites = []

    if not name:
        return jsonify({"ok": False, "error": "领域名称不能为空"}), 400

    with UserDB() as db:
        new_id = db.create_domain(user["id"], name, description, is_system=0, ref_websites=ref_websites)
        if new_id:
            return jsonify({"ok": True, "id": new_id})
        else:
            return jsonify({"ok": False, "error": "领域名称已存在或创建失败"}), 500


@app.route("/api/domains/<int:domain_id>", methods=["PUT"])
def api_update_domain(domain_id: int):
    """更新领域分类"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    name = data.get("name")
    description = data.get("description")
    ref_websites = data.get("ref_websites")  # None 表示不更新
    if ref_websites is not None and not isinstance(ref_websites, list):
        ref_websites = []

    if name is None and description is None and ref_websites is None:
        return jsonify({"ok": False, "error": "没有提供更新内容"}), 400

    with UserDB() as db:
        if db.update_domain(domain_id, user["id"], name, description, ref_websites):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "更新失败（系统领域不可改名）"}), 400


@app.route("/api/domains/<int:domain_id>", methods=["DELETE"])
def api_delete_domain(domain_id: int):
    """删除领域分类（系统领域不可删除）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        if db.delete_domain(domain_id, user["id"]):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "删除失败（系统领域不可删除）"}), 400


# ════════════════════════════════════════════════════════════
# API：AI 模型管理
# ════════════════════════════════════════════════════════════

@app.route("/api/ai_models", methods=["GET"])
def api_get_ai_models():
    """获取用户的所有AI模型"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        models = db.get_user_ai_models(user["id"])
        # 不返回敏感信息（api_key）
        for model in models:
            model.pop("api_key", None)
        return jsonify({"ok": True, "models": models})


@app.route("/api/ai_models/<int:model_id>/set_default", methods=["POST"])
def api_set_default_ai_model(model_id: int):
    """设置默认AI模型"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        if db.set_default_ai_model(user["id"], model_id):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "设置失败"}), 500


@app.route("/api/ai_models/<int:model_id>", methods=["GET"])
def api_get_ai_model(model_id: int):
    """获取指定AI模型详情"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        model = db.get_ai_model_by_id(model_id, user["id"])
        if model:
            # 不返回敏感信息（api_key）
            model.pop("api_key", None)
            return jsonify({"ok": True, "model": model})
        else:
            return jsonify({"ok": False, "error": "模型不存在"}), 404


@app.route("/api/ai_models", methods=["POST"])
def api_create_ai_model():
    """创建AI模型"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    name = data.get("name", "").strip()
    provider = data.get("provider", "").strip()
    model_name = data.get("model_name", "").strip()
    api_key = data.get("api_key", "").strip()
    api_base = data.get("api_base", "").strip()
    is_default = data.get("is_default", False)
    is_image_model = data.get("is_image_model", False)

    # 验证必填字段
    if not name:
        return jsonify({"ok": False, "error": "模型名称不能为空"}), 400
    if not provider:
        return jsonify({"ok": False, "error": "提供商不能为空"}), 400
    if not model_name:
        return jsonify({"ok": False, "error": "模型名称不能为空"}), 400
    if not api_key:
        return jsonify({"ok": False, "error": "API密钥不能为空"}), 400

    with UserDB() as db:
        new_id = db.create_ai_model(
            user["id"], name, provider, model_name, api_key, api_base, is_default, is_image_model
        )
        if new_id:
            return jsonify({"ok": True, "id": new_id})
        else:
            return jsonify({"ok": False, "error": "模型名称已存在或创建失败"}), 500


@app.route("/api/ai_models/<int:model_id>", methods=["PUT"])
def api_update_ai_model(model_id: int):
    """更新AI模型"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    name = data.get("name")
    provider = data.get("provider")
    model_name = data.get("model_name")
    api_key = data.get("api_key")
    api_base = data.get("api_base")
    is_image_model = data.get("is_image_model")

    if all(v is None for v in [name, provider, model_name, api_key, api_base, is_image_model]):
        return jsonify({"ok": False, "error": "没有提供更新内容"}), 400

    with UserDB() as db:
        if db.update_ai_model(model_id, user["id"], name, provider, model_name, api_key, api_base, is_image_model):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "更新失败"}), 500


@app.route("/api/ai_models/<int:model_id>", methods=["DELETE"])
def api_delete_ai_model(model_id: int):
    """删除AI模型"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        if db.delete_ai_model(model_id, user["id"]):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": "删除失败"}), 500


# ════════════════════════════════════════════════════════════
# API：SSE 实时日志
# ════════════════════════════════════════════════════════════

@app.route("/api/logs/<task_id>")
def api_logs(task_id: str):
    """Server-Sent Events 日志流"""
    q: queue.Queue = _log_queues.get(task_id)
    if q is None:
        return Response("data: {\"msg\":\"task not found\",\"level\":\"error\"}\n\n",
                        mimetype="text/event-stream")

    def generate():
        while True:
            try:
                item = q.get(timeout=30)
                if item is None:   # 哨兵值：任务结束
                    yield f"data: {json.dumps({'msg':'__DONE__','level':'done'})}\n\n"
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield "data: {\"msg\":\"ping\",\"level\":\"ping\"}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ════════════════════════════════════════════════════════════
# API：自动选题
# ════════════════════════════════════════════════════════════

@app.route("/api/topics", methods=["POST"])
def api_get_topics():
    data = request.json or {}
    task_id = data.get("task_id", "topics")
    no_cache = data.get("no_cache", False)

    account_id = data.get("account_id", "")
    acc_cfg = get_account_config(account_id)
    prompt = data.get("topic_prompt") or acc_cfg.get("topic_prompt", "")
    # domain 仅作为 AI 背景提示，不决定爬哪些网站；留空则由 AI 从 prompt 自行判断

    # 在主线程里预先获取 user_id（子线程无法访问 Flask g）
    session_id = _get_session_id()
    current_user = get_current_user(session_id)
    current_user_id = current_user["id"] if current_user else 1

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            from modules.auto_selector import generate_topics
            topics = generate_topics(
                prompt=prompt,
                domain=acc_cfg.get("domain", ""),  # 传入账号领域，降级时按领域爬取
                search_queries=[],  # 固定传空数组，使用 AI 生成
                max_topics=10,
                cache_hours=0,  # 始终不使用缓存，强制重新搜索
                user_id=current_user_id,
            )
            push_log(task_id, json.dumps({"topics": topics}, ensure_ascii=False), "result")
        except Exception as e:
            push_log(task_id, f"❌ 错误：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)  # 结束哨兵

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# API：AI 生成文章
# ════════════════════════════════════════════════════════════

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.json or {}
    task_id = data.get("task_id", "generate")

    topic = data.get("topic", {})
    account_id = data.get("account_id", "")
    acc_cfg = get_account_config(account_id)

    style = data.get("style") or acc_cfg.get("article_style", "观点评论")
    words = int(data.get("word_count") or acc_cfg.get("word_count", 2000))
    custom_writing_prompt = acc_cfg.get("writing_prompt", "")
    ending_text = acc_cfg.get("ending_text", "感谢阅读，我们下期见。")

    extra = data.get("extra_instructions", "")
    skill_id = data.get("skill_id")  # 写作技能 ID（可选）

    # 在主线程里预先获取 user_id（子线程无法访问 Flask g）
    session_id = _get_session_id()
    current_user = get_current_user(session_id)
    current_user_id = current_user["id"] if current_user else 1

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            from modules.ai_writer import generate_article, _check_history_duplicates

            # 历史文章去重检查（三重检测：标题bigram + 产品型号名 + 内容bigram）
            topic_title = topic.get("title", "")
            topic_content = topic.get("summary", "") + topic.get("detail", "")
            dupes = _check_history_duplicates(current_user_id, topic_title, topic_content)
            dup_warning = ""
            if dupes:
                dup_titles = "、".join([f"「{d['title']}」({d['reason']})" for d in dupes[:3]])
                dup_warning = f"\n\n⚠️ **历史文章去重提醒**：系统检测到以下相似历史文章：{dup_titles}。请务必写出与以上文章**完全不同**的角度、观点和内容，避免重复写稿。"
                print(f"   ⚠️  检测到 {len(dupes)} 篇相似历史文章：{', '.join([d['title']+'（'+d['reason']+'）' for d in dupes[:3]])}")

            # 如果选择了写作技能，加载技能提示词
            skill_prompt = ""
            if skill_id:
                try:
                    from modules.user_db import UserDB as _UDB
                    with _UDB() as _sdb:
                        _skill = _sdb.get_skill_by_id(int(skill_id), current_user_id)
                    if _skill:
                        skill_prompt = _skill["prompt_content"]
                        print(f"🎯 使用写作技能：{_skill['name']}")
                    else:
                        print(f"⚠️  未找到技能 ID={skill_id}，忽略技能")
                except Exception as _se:
                    print(f"⚠️  加载写作技能失败（{_se}），忽略技能")

            md_content, saved_path = generate_article(
                topic=topic,
                style=style,
                word_count=words,
                extra_instructions=extra + dup_warning,
                save_to_file=True,
                custom_writing_prompt=custom_writing_prompt,
                ending_text=ending_text,
                user_id=current_user_id,
                skill_prompt=skill_prompt,
            )

            # 爆款标题替换
            try:
                from modules.article_rewriter import generate_title as gen_viral_title
                import re as _re
                body_text = _re.sub(r'^#\s+.+\n*', '', md_content, count=1)
                viral_title = gen_viral_title(body_text, user_id=current_user_id)
                if viral_title and viral_title.strip():
                    md_content = _re.sub(r'^#\s+.+\n*', f'# {viral_title.strip()}\n\n', md_content, count=1)
                    if saved_path:
                        with open(saved_path, "w", encoding="utf-8") as _f:
                            _f.write(md_content)
                    print(f"   🔥 爆款标题：{viral_title.strip()}")
                else:
                    print(f"   ⚠️  爆款标题生成失败，保留原标题")
            except Exception as _e:
                print(f"   ⚠️  爆款标题生成异常（{_e}），保留原标题")

            # AI 排版优化
            try:
                from modules.ai_writer import ai_format_article
                formatted_md = ai_format_article(md_content, user_id=current_user_id)
                if formatted_md != md_content:
                    md_content = formatted_md
                    if saved_path:
                        with open(saved_path, "w", encoding="utf-8") as _f:
                            _f.write(md_content)
            except Exception as _e:
                print(f"   ⚠️  AI 排版异常（{_e}），保留原文")

            # 保存文章到数据库
            account_db_id = acc_cfg.get("id", 0)
            print(f"🔍 调试：account_db_id={account_db_id}, saved_path='{saved_path}'")
            if account_db_id > 0 and saved_path:
                try:
                    from modules.user_db import UserDB
                    db = UserDB()

                    # 从 Markdown 内容提取标题
                    import re
                    title_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
                    title = title_match.group(1).strip() if title_match else topic.get("title", "未命名")

                    # 从完整路径提取文件名（只存文件名到数据库）
                    file_name_only = Path(saved_path).name

                    article_id = db.create_article(
                        user_id=current_user_id,
                        account_db_id=account_db_id,
                        title=title,
                        file_path=file_name_only,  # 只存文件名
                        status="draft",
                    )

                    if article_id:
                        push_log(task_id, f"💾 文章已保存到数据库（ID: {article_id}）", "info")
                    else:
                        push_log(task_id, "⚠️  保存文章到数据库失败", "warning")
                except Exception as e:
                    push_log(task_id, f"⚠️  保存文章到数据库时出错：{e}", "warning")
            else:
                if account_db_id <= 0:
                    push_log(task_id, f"⚠️  跳过保存到数据库：无效的 account_db_id={account_db_id}", "warning")
                if not saved_path:
                    push_log(task_id, f"⚠️  跳过保存到数据库：saved_path 为空", "warning")

            push_log(task_id, json.dumps({
                "md_content": md_content,
                "saved_path": saved_path,
            }, ensure_ascii=False), "result")
        except Exception as e:
            push_log(task_id, f"❌ 错误：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# API：链接改写（抓取 URL → AI 改写为原创文章）
# ════════════════════════════════════════════════════════════

@app.route("/api/fetch_url", methods=["POST"])
def api_fetch_url():
    """抓取 URL 内容，返回标题和正文"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"ok": False, "error": "请输入文章链接"}), 400

    try:
        from modules.article_rewriter import fetch_url_content
        title, content = fetch_url_content(url)
        return jsonify({"ok": True, "title": title, "content": content})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"抓取失败：{e}"}), 500


@app.route("/api/rewrite", methods=["POST"])
def api_rewrite():
    """AI 改写文章（SSE 实时日志）"""
    data = request.json or {}
    task_id = data.get("task_id", "rewrite")

    original_title = data.get("original_title", "")
    original_content = data.get("original_content", "")
    account_id = data.get("account_id", "")
    word_count = int(data.get("word_count", 2000))
    extra_instructions = data.get("extra_instructions", "")

    acc_cfg = get_account_config(account_id)
    style = data.get("style") or acc_cfg.get("article_style", "观点评论")
    custom_writing_prompt = acc_cfg.get("writing_prompt", "")

    if not original_content:
        return jsonify({"ok": False, "error": "没有原文内容"}), 400

    # 预先获取 user_id
    session_id = _get_session_id()
    current_user = get_current_user(session_id)
    current_user_id = current_user["id"] if current_user else 1

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            print(f"   [1/2] 开始 AI 改写...")

            from modules.article_rewriter import rewrite_article
            md_content = rewrite_article(
                original_title=original_title,
                original_content=original_content,
                user_id=current_user_id,
                word_count=word_count,
                style=style,
                custom_writing_prompt=custom_writing_prompt,
                extra_instructions=extra_instructions,
            )

            print(f"   [2/2] 改写完成！")

            # 保存 Markdown 文件
            from datetime import datetime
            from modules.ai_writer import OUTPUT_DIR
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r'[^\w\u4e00-\u9fff]+', '_', original_title or "rewrite")[:30]
            filename = f"{timestamp}_{safe_title}.md"
            saved_path = str(OUTPUT_DIR / filename)
            with open(saved_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"   文章已保存：{saved_path}")

            # 保存到数据库
            account_db_id = acc_cfg.get("id", 0)
            if account_db_id > 0 and saved_path:
                try:
                    title_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
                    title = title_match.group(1).strip() if title_match else "改写文章"
                    file_name_only = Path(saved_path).name

                    db = UserDB()
                    article_id = db.create_article(
                        user_id=current_user_id,
                        account_db_id=account_db_id,
                        title=title,
                        file_path=file_name_only,
                        status="draft",
                    )
                    if article_id:
                        push_log(task_id, f"   文章已保存到数据库（ID: {article_id}）", "info")
                except Exception as e:
                    push_log(task_id, f"   保存文章到数据库时出错：{e}", "warning")

            push_log(task_id, json.dumps({
                "md_content": md_content,
                "saved_path": saved_path,
            }, ensure_ascii=False), "result")

        except Exception as e:
            push_log(task_id, f"   改写失败：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# API：全自动流水线（选题 → 写作 → 生成草稿）
# ════════════════════════════════════════════════════════════

@app.route("/api/auto", methods=["POST"])
def api_auto():
    data = request.json or {}
    task_id = data.get("task_id", "auto")
    no_cache = data.get("no_cache", False)
    account_id = data.get("account_id", "")
    skill_id = data.get("skill_id")  # 写作技能 ID（可选）

    # 在主线程里预先获取 user_id 和账号配置（子线程无法访问 Flask g）
    session_id = _get_session_id()
    current_user = get_current_user(session_id)
    current_user_id = current_user["id"] if current_user else 1
    acc_cfg = get_account_config(account_id)

    # 如果选择了写作技能，预先加载技能提示词
    skill_prompt = ""
    if skill_id:
        try:
            from modules.user_db import UserDB as _UDB
            with _UDB() as _sdb:
                _skill = _sdb.get_skill_by_id(int(skill_id), current_user_id)
            if _skill:
                skill_prompt = _skill["prompt_content"]
        except Exception:
            pass

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            import main as m
            cfg = m.load_config()
            # acc_cfg 已在主线程获取，直接使用（子线程无法访问 Flask g）

            # 构建用于 run_auto_pipeline 的 prompt_cfg（search_queries 已废弃）
            prompt_cfg = {
                "topic_prompt": acc_cfg.get("topic_prompt", ""),
                "search_queries": [],  # 固定传空数组，使用 AI 生成
                "article_style": acc_cfg.get("article_style", "观点评论"),
                "word_count": acc_cfg.get("word_count", 2000),
                "theme": acc_cfg.get("theme", "blue"),
                "writing_prompt": acc_cfg.get("writing_prompt", ""),
            }

            # 允许前端覆盖参数（优先级高于账号配置）
            if data.get("style"):
                prompt_cfg["article_style"] = data["style"]
            if data.get("word_count"):
                prompt_cfg["word_count"] = int(data["word_count"])
            if data.get("topic_index"):
                topic_index = int(data["topic_index"])
            else:
                topic_index = None

            theme = data.get("theme") or prompt_cfg.get("theme", acc_cfg.get("default_theme", "blue"))

            account_db_id = acc_cfg.get("id", 0)

            result = m.run_auto_pipeline(
                config=cfg,
                prompt_cfg=prompt_cfg,
                draft_only=True,
                topic_index=topic_index,
                style_override=prompt_cfg.get("article_style", ""),
                words_override=prompt_cfg.get("word_count", 0),
                theme_override=theme,
                cache_hours=0,  # 始终不使用缓存，强制重新搜索
                custom_writing_prompt=prompt_cfg.get("writing_prompt", ""),
                account_db_id=acc_cfg.get("id", 0),
                user_id=current_user_id,
                domain_override=acc_cfg.get("domain", ""),
                skill_prompt=skill_prompt,
            )

            push_log(task_id, json.dumps(result, ensure_ascii=False), "result")
        except Exception as e:
            push_log(task_id, f"❌ 错误：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# API：统计数据
# ════════════════════════════════════════════════════════════

@app.route("/api/stats", methods=["GET"])
def api_stats():
    """获取用户统计数据（从数据库）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)

    if not user:
        return jsonify({
            "total_articles": 0,
            "draft_articles": 0,
            "published_articles": 0,
            "today_articles": 0,
            "weekly_data": [],
            "weekly_account_data": [],
            "account_stats": [],
            "keyword_top10": [],
            "account_7d_stats": [],
            "status_funnel": [],
            "status_distribution": [],
            "hourly_data": [],
            "monthly_data": [],
            "account_rank": [],
            "keyword_cloud": [],
        })

    with UserDB() as db:
        stats = db.get_user_stats(user["id"])

    return jsonify({
        "total_articles": stats["total_articles"],
        "draft_articles": stats["draft_articles"],
        "published_articles": stats["published_articles"],
        "today_articles": stats["today_articles"],
        "weekly_data": stats["weekly_data"],
        "weekly_account_data": stats.get("weekly_account_data", []),
        "account_stats": stats["account_stats"],
        "keyword_top10": stats.get("keyword_top10", []),
        "account_7d_stats": stats.get("account_7d_stats", []),
        "status_funnel": stats.get("status_funnel", []),
        "status_distribution": stats.get("status_distribution", []),
        "hourly_data": stats.get("hourly_data", []),
        "monthly_data": stats.get("monthly_data", []),
        "account_rank": stats.get("account_rank", []),
        "keyword_cloud": stats.get("keyword_cloud", []),
    })


# ════════════════════════════════════════════════════════════
# API：历史文章列表
# ════════════════════════════════════════════════════════════

@app.route("/api/articles", methods=["GET"])
def api_list_articles():
    """获取历史文章列表（从数据库，支持分页）

    查询参数：
    - page: 页码，默认 1
    - page_size: 每页数量，默认 10
    - account_id: 可选，账号 ID（字符串类型），如果提供则只返回该账号的文章
    """
    try:
        session_id = _get_session_id()
        user = get_current_user(session_id)
        if not user:
            return jsonify({"articles": [], "pagination": {}})  # 未登录返回空列表

        # 获取查询参数
        page = request.args.get("page", type=int, default=1)
        page_size = request.args.get("page_size", type=int, default=10)
        account_id = request.args.get("account_id")
        keyword = request.args.get("keyword", "").strip()
    except Exception as e:
        import traceback
        print(f"[API ERROR] 获取参数失败: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "articles": [], "pagination": {}}), 500

    try:
        # 从 article_history 读取（协同创作产出的完整文章）
        result = list_articles_paginated(
            user["id"], page=page, page_size=page_size, keyword=keyword or None
        )
        articles = result["articles"]
        pagination = result["pagination"]
        print(f"[API] 加载文章列表: 用户 {user['id']}, 文章数 {len(articles)}, 总数 {pagination.get('total')}")
    except Exception as e:
        import traceback
        print(f"[API ERROR] 数据库查询失败: {e}")
        print(traceback.print_exc())
        return jsonify({"error": str(e), "articles": [], "pagination": {}}), 500

    items = []
    for art in articles:
        # 文章大小：以 content_json 长度估算
        content = art.get("content") or ""
        size = len(content.encode("utf-8")) if isinstance(content, str) else 0

        items.append({
            "id": art["id"],
            "filename": f"{art['id']}.md",
            "title": art.get("title") or "无标题",
            "status": "saved",
            "account_name": "协同创作",
            "size": size,
            "mtime": art.get("created_at") or "",
            "created_at": art.get("created_at") or "",
        })

    return jsonify({"articles": items, "pagination": pagination})


@app.route("/api/articles/<filename>", methods=["GET"])
def api_get_article(filename: str):
    """读取单篇文章内容（Markdown），同时返回服务器绝对路径供前端推送时复用"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    # 处理 URL 编码的文件名
    from urllib.parse import unquote
    filename = unquote(filename)

    # 如果传入的是完整路径，提取纯文件名
    if "/" in filename or "\\" in filename:
        filename = Path(filename).name

    p = BASE_DIR / "output" / "articles" / filename
    if not p.exists() or not p.suffix == ".md":
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "md_text":     p.read_text(encoding="utf-8"),
        "server_path": str(p),   # 前端推送时带上，后端直接读文件不再新建
    })


@app.route("/api/articles/<filename>", methods=["PUT"])
def api_save_article(filename: str):
    """保存编辑后的文章内容"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    p = BASE_DIR / "output" / "articles" / filename
    if not p.exists():
        return jsonify({"error": "not found"}), 404
    data = request.json or {}
    p.write_text(data.get("md_text", ""), encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/articles/<filename>", methods=["DELETE"])
def api_delete_article(filename: str):
    """删除单篇历史文章（.md 文件）并同步删除对应 HTML 草稿"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    # 只允许删 output/articles/ 下的 .md 文件，防止路径穿越
    if ".." in filename or "/" in filename or not filename.endswith(".md"):
        return jsonify({"error": "invalid filename"}), 400
    p = BASE_DIR / "output" / "articles" / filename
    if not p.exists():
        return jsonify({"error": "not found"}), 404

    stem = Path(filename).stem  # 去掉 .md 后缀的文件名
    p.unlink()

    # 同步删除 output/drafts/ 下同名的 HTML 草稿
    # 用 startswith 而不是 glob，避免文件名含中文/特殊字符时 glob 匹配失败
    drafts_dir = BASE_DIR / "output" / "drafts"
    deleted_html = []
    if drafts_dir.exists():
        for html_file in drafts_dir.iterdir():
            if html_file.suffix == ".html" and html_file.stem.startswith(stem):
                html_file.unlink()
                deleted_html.append(html_file.name)

    # 同步删除数据库记录
    with UserDB() as db:
        db.delete_article_by_filename(filename, user["id"])

    print(f"[DELETE] 已删除 {filename}，同步删除 HTML：{deleted_html}")
    return jsonify({"ok": True, "deleted_html": deleted_html})


# ════════════════════════════════════════════════════════════
# API：封面列表
# ════════════════════════════════════════════════════════════

@app.route("/api/covers/<filename>")
def api_get_cover(filename: str):
    covers_dir = BASE_DIR / "output" / "covers"
    return send_from_directory(str(covers_dir), filename)


# ════════════════════════════════════════════════════════════
# API：HTML 预览文件
# ════════════════════════════════════════════════════════════

@app.route("/api/drafts/<filename>")
def api_get_draft(filename: str):
    drafts_dir = BASE_DIR / "output" / "drafts"
    return send_from_directory(str(drafts_dir), filename)


# ════════════════════════════════════════════════════════════
# API：AI 排版（优化 Markdown 格式）
# ════════════════════════════════════════════════════════════

@app.route("/api/format", methods=["POST"])
def api_format():
    """使用 AI 优化 Markdown 文章的排版和语言风格"""
    data = request.json or {}
    task_id = data.get("task_id", "format")
    md_text = data.get("md_text", "")

    if not md_text:
        return jsonify({"ok": False, "error": "请提供 md_text"}), 400

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            from modules.ai_writer import _detect_llm_backend, _call_openai, _call_ollama

            push_log(task_id, "🔍 检测 AI 服务...", "info")

            backend, config = _detect_llm_backend()

            if backend == "template":
                push_log(task_id, "❌ 未检测到 AI 服务，无法使用 AI 排版功能", "error")
                push_log(task_id, "", "end")
                return

            push_log(task_id, f"✅ 使用 AI 服务: {backend}", "info")
            push_log(task_id, "📝 正在优化排版...", "info")

            # AI 排版提示词
            prompt = f"""请优化以下 Markdown 文章的排版和语言风格。

要求：
1. 保持原有的核心内容和观点不变
2. 优化语言表达，使其更自然流畅，去除AI味儿
3. 改善段落结构，使逻辑更清晰
4. **必须保留原有的所有 ## 小标题，不能删除任何一个；如果原文没有 ## 小标题，必须添加 2～4 个 ## 小标题来划分段落层次**
5. 保持 Markdown 格式正确（全文标题用 # ，段落小标题用 ## ，更细分用 ### ）
6. 不要改变原文的主旨和重要信息
7. 不要添加任何额外的客套话或总结语

待优化的文章：

{md_text}

请直接返回优化后的 Markdown 内容，不要有任何解释或说明。"""

            if backend == "openai":
                result = _call_openai(prompt, config)
            elif backend == "ollama":
                result = _call_ollama(prompt, config)
            else:
                push_log(task_id, "❌ 不支持的 AI 后端", "error")
                push_log(task_id, "", "end")
                return

            push_log(task_id, "✅ 排版优化完成", "info")
            push_log(task_id, json.dumps({"formatted_md": result}, ensure_ascii=False), "result")

        except Exception as e:
            push_log(task_id, f"❌ 错误：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})



# ════════════════════════════════════════════════════════════
# API：每日热搜榜
# ════════════════════════════════════════════════════════════

@app.route("/api/hotrank/<platform_id>", methods=["GET"])
def api_hotrank(platform_id: str):
    """获取指定平台热搜榜"""
    from modules.hotrank import get_hotrank, PLATFORMS
    data = get_hotrank(platform_id)
    return jsonify(data)


@app.route("/api/hotrank", methods=["GET"])
def api_hotrank_platforms():
    """获取所有平台列表"""
    from modules.hotrank import PLATFORMS
    return jsonify({
        "ok": True,
        "platforms": [{"id": p["id"], "name": p["name"], "icon": p["icon"]} for p in PLATFORMS],
    })


# ════════════════════════════════════════════════════════════
# API：历史上的今天
# ════════════════════════════════════════════════════════════

@app.route("/api/today_in_history", methods=["GET"])
def api_today_in_history():
    """获取历史上的今天数据"""
    from modules.today_in_history import get_today_in_history
    try:
        data = get_today_in_history()
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ════════════════════════════════════════════════════════════
# API：AI 助手
# ════════════════════════════════════════════════════════════

@app.route("/api/ai_assistant/chat", methods=["POST"])
def api_ai_assistant_chat():
    """AI 助手对话接口"""
    from modules.ai_assistant import quick_chat, add_to_history
    
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401
    
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    mode = data.get("mode", "chat")
    
    if not message:
        return jsonify({"ok": False, "error": "消息不能为空"}), 400
    
    try:
        # 传递 user_id 以读取数据库中的 AI 配置
        result = quick_chat(message, mode=mode, user_id=user["id"])
        
        if result.get("ok"):
            # 保存到历史
            add_to_history(session_id, "user", message)
            add_to_history(session_id, "assistant", result.get("content", ""))
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ai_assistant/clear", methods=["POST"])
def api_ai_assistant_clear():
    """清空对话历史"""
    from modules.ai_assistant import clear_history
    
    session_id = _get_session_id() or "anonymous"
    clear_history(session_id)
    
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
# API：素材库
# ════════════════════════════════════════════════════════════

@app.route("/api/material_library", methods=["GET"])
def api_get_materials():
    """获取素材库列表"""
    from modules.material_library import get_materials

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    tag = request.args.get("tag")
    source_type = request.args.get("source_type")
    keyword = request.args.get("keyword")
    group_id = request.args.get("group_id")
    page = request.args.get("page", type=int, default=1)
    page_size = request.args.get("page_size", type=int, default=20)

    offset = (page - 1) * page_size

    result = get_materials(
        user_id=user["id"],
        tag=tag,
        source_type=source_type,
        keyword=keyword,
        group_id=group_id,
        limit=page_size,
        offset=offset,
    )
    return jsonify(result)


@app.route("/api/material_library", methods=["POST"])
def api_add_material():
    """收藏到素材库"""
    from modules.material_library import add_to_library

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    title = data.get("title", "").strip()
    tags = data.get("tags", "").strip()
    source_type = data.get("source_type", "cover")
    source_id = data.get("source_id")
    filename = data.get("filename", "").strip()
    image_url = data.get("image_url", "").strip()
    prompt = data.get("prompt", "").strip()
    notes = data.get("notes", "").strip()
    group_id = data.get("group_id")

    if not filename:
        return jsonify({"ok": False, "error": "文件名不能为空"}), 400

    result = add_to_library(
        user_id=user["id"],
        title=title,
        tags=tags,
        source_type=source_type,
        source_id=source_id,
        filename=filename,
        image_url=image_url,
        prompt=prompt,
        notes=notes,
        group_id=group_id,
    )
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/material_library/<int:material_id>", methods=["GET"])
def api_get_material(material_id: int):
    """获取单个素材详情"""
    from modules.material_library import get_material_by_id

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    item = get_material_by_id(material_id, user["id"])
    if item:
        return jsonify({"ok": True, **item})
    else:
        return jsonify({"ok": False, "error": "素材不存在"}), 404


@app.route("/api/material_library/<int:material_id>", methods=["PUT"])
def api_update_material(material_id: int):
    """更新素材信息"""
    from modules.material_library import update_material

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    title = data.get("title")
    tags = data.get("tags")
    notes = data.get("notes")

    success = update_material(material_id, user["id"], title, tags, notes)
    if success:
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "更新失败"}), 500


@app.route("/api/material_library/<int:material_id>", methods=["DELETE"])
def api_delete_material(material_id: int):
    """删除素材"""
    from modules.material_library import delete_material

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    success = delete_material(material_id, user["id"])
    if success:
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "删除失败"}), 500


@app.route("/api/material_library/tags", methods=["GET"])
def api_get_material_tags():
    """获取素材库所有标签"""
    from modules.material_library import get_all_tags

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    tags = get_all_tags(user["id"])
    return jsonify({"ok": True, "tags": tags})


@app.route("/api/material_library/image/<filename>")
def api_material_library_image(filename):
    """提供素材库图片"""
    from modules.material_library import MATERIAL_DIR

    # 安全检查：允许 mat_ / upload_ / img_（AI 配图生成）前缀
    allowed_prefix = ("mat_", "upload_", "img_")
    if not any(filename.startswith(p) for p in allowed_prefix) or ".." in filename:
        return "Forbidden", 403

    return send_from_directory(str(MATERIAL_DIR), filename)


@app.route("/api/material_library/generate", methods=["POST"])
def api_generate_image():
    """AI 配图：根据文字描述生成文章插图并收藏到素材库。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.json or {}
    prompt = (data.get("prompt") or "").strip()
    size = data.get("size") or "1024x1024"

    from modules.image_generator import generate_image
    result = generate_image(prompt=prompt, user_id=user["id"], size=size)
    if not result.get("ok"):
        return jsonify(result), 400

    return jsonify(result)


@app.route("/api/material_library/upload", methods=["POST"])
def api_upload_material():
    """上传本地图片到素材库"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "未选择文件"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "未选择文件"}), 400

    from modules.material_library import upload_image

    title = request.form.get("title", "").strip()
    tags = request.form.get("tags", "").strip()
    group_id = request.form.get("group_id", type=int)
    notes = request.form.get("notes", "").strip()

    result = upload_image(
        user_id=user["id"],
        file_data=file.read(),
        original_filename=file.filename,
        title=title,
        tags=tags,
        group_id=group_id,
        notes=notes,
    )

    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


# ── 素材分组 API ──────────────────────────────────────────

@app.route("/api/material_groups", methods=["GET"])
def api_get_material_groups():
    """获取素材分组列表"""
    from modules.material_library import get_groups

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    groups = get_groups(user["id"])
    return jsonify({"ok": True, "data": groups})


@app.route("/api/material_groups", methods=["POST"])
def api_create_material_group():
    """创建素材分组"""
    from modules.material_library import create_group

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    name = data.get("name", "").strip()
    sort_order = data.get("sort_order", 0)

    if not name:
        return jsonify({"ok": False, "error": "分组名称不能为空"}), 400

    result = create_group(user["id"], name, sort_order)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/material_groups/<int:group_id>", methods=["PUT"])
def api_update_material_group(group_id: int):
    """更新素材分组"""
    from modules.material_library import update_group

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    name = data.get("name")
    sort_order = data.get("sort_order")

    result = update_group(group_id, user["id"], name=name, sort_order=sort_order)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/material_groups/<int:group_id>", methods=["DELETE"])
def api_delete_material_group(group_id: int):
    """删除素材分组"""
    from modules.material_library import delete_group

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    move_to_none = request.args.get("move", "true") == "true"
    result = delete_group(group_id, user["id"], move_to_none=move_to_none)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.route("/api/material_library/<int:material_id>/move", methods=["POST"])
def api_move_material(material_id: int):
    """移动素材到指定分组"""
    from modules.material_library import move_material_to_group

    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    data = request.get_json() or {}
    group_id = data.get("group_id")  # None = 移到未分组

    result = move_material_to_group(material_id, user["id"], group_id=group_id)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


# ════════════════════════════════════════════════════════════
# API：链接改写 V2（五步流水线）
# ════════════════════════════════════════════════════════════

@app.route("/api/rewrite_v2", methods=["POST"])
def api_rewrite_v2():
    """
    链接改写 V2 — 五步流水线：
      1. 提取链接内容
      2. AI 观点提取（风格 + 摘要 + 核心观点）
      3. AI 文章仿写
      4. AI 爆款标题生成
      5. 文章排版（Markdown → 带内联样式的 HTML）
    """
    data = request.json or {}
    task_id = data.get("task_id", "rewrite_v2")
    url = data.get("url", "").strip()
    content = data.get("content", "").strip()
    extra_instructions = data.get("extra_instructions", "")

    if not url and not content:
        return jsonify({"ok": False, "error": "请提供文章链接或文章内容"}), 400

    # 预先获取 user_id
    session_id = _get_session_id()
    current_user = get_current_user(session_id)
    current_user_id = current_user["id"] if current_user else 1

    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            from modules.article_rewriter import run_rewrite_pipeline

            def on_step(step_num, step_name, step_data):
                """步骤回调，推送进度到前端"""
                step_msg = {"step": step_num, "name": step_name}
                if isinstance(step_data, dict):
                    # 步骤完成：把含数据的完整 dict 序列化成 JSON 推送给前端
                    step_msg.update(step_data)
                    push_log(task_id, json.dumps(step_msg, ensure_ascii=False), "result")
                else:
                    # 步骤开始执行（step_data 为 None），通知前端切换为 running 状态
                    push_log(task_id, json.dumps(step_msg, ensure_ascii=False), "running")
                push_log(task_id, f"   [{step_num}/7] {step_name}", "info")

            print(f"   🚀 开始五步改写流水线...")
            result = run_rewrite_pipeline(
                url=url,
                content=content,
                user_id=current_user_id,
                extra_instructions=extra_instructions,
                on_step=on_step,
            )

            # 推送最终完整结果
            final_result = {
                "title": result.get("title", ""),
                "article_body": result.get("article_body", ""),
                "wechat_html": result.get("wechat_html", ""),
                "analysis": result.get("analysis", {}),
                "original_title": result.get("original_title", ""),
            }

            # 保存 Markdown 文件
            from datetime import datetime
            from modules.ai_writer import OUTPUT_DIR
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r'[^\w\u4e00-\u9fff]+', '_', result.get("title", "rewrite")[:30])
            filename = f"{timestamp}_{safe_title}.md"
            saved_path = str(OUTPUT_DIR / filename)

            full_md = f"# {result.get('title', '')}\n\n{result.get('article_body', '')}"
            with open(saved_path, "w", encoding="utf-8") as f:
                f.write(full_md)

            final_result["saved_path"] = saved_path

            # 保存到数据库
            acc_cfg = get_account_config(data.get("account_id", ""))
            account_db_id = acc_cfg.get("id", 0) if acc_cfg else 0
            if account_db_id > 0 and saved_path:
                try:
                    db = UserDB()
                    article_id = db.create_article(
                        user_id=current_user_id,
                        account_db_id=account_db_id,
                        title=result.get("title", "改写文章"),
                        file_path=Path(saved_path).name,
                        status="draft",
                    )
                    if article_id:
                        push_log(task_id, f"   文章已保存到数据库（ID: {article_id}）", "info")
                except Exception as e:
                    push_log(task_id, f"   保存文章到数据库时出错：{e}", "warning")

            push_log(task_id, json.dumps(final_result, ensure_ascii=False), "result")

            push_log(task_id, "   ✅ 全部流水线完成！", "done")

        except Exception as e:
            push_log(task_id, f"   ❌ 流水线失败：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


# ════════════════════════════════════════════════════════════
# 协同创作
# ════════════════════════════════════════════════════════════

def _parse_json_column(value):
    """解析 DB 中的 JSON 文本列，NULL/空值返回 None。"""
    if not value:
        return None
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return None


def _row_to_project(row):
    """将 collaborative_projects 行字典转换为 API project 对象。"""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "current_phase": row["current_phase"],
        "topic": _parse_json_column(row["topic_json"]),
        "outline": _parse_json_column(row["outline_json"]),
        "content": _parse_json_column(row["content_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.route("/collaborative")
def collaborative_list():
    """协同创作入口：直跳最近的工作台项目，无项目则自动创建。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")

    with UserDB() as db:
        cur = db.conn.cursor()
        # 取最近活跃的一个项目
        cur.execute(
            "SELECT id FROM collaborative_projects "
            "WHERE user_id = ? "
            "ORDER BY updated_at DESC, id DESC LIMIT 1",
            (user["id"],),
        )
        row = cur.fetchone()

    if row:
        return redirect(f"/collaborative/{row['id']}")

    # 没有项目则自动创建一个，直入工作台
    with UserDB() as db:
        cur = db.conn.cursor()
        cur.execute(
            "INSERT INTO collaborative_projects (user_id, title, current_phase) "
            "VALUES (?, ?, ?)",
            (user["id"], "未命名创作", "topic"),
        )
        db.conn.commit()
        new_id = cur.lastrowid

    return redirect(f"/collaborative/{new_id}")


@app.route("/api/collaborative/create", methods=["POST"])
def api_collaborative_create():
    """为当前用户创建一个协同创作项目。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json() or {}
    title = data.get("title") or "未命名创作"

    with UserDB() as db:
        cur = db.conn.cursor()
        cur.execute(
            "INSERT INTO collaborative_projects (user_id, title, current_phase) VALUES (?, ?, ?)",
            (user["id"], title, "topic"),
        )
        db.conn.commit()
        new_id = cur.lastrowid
        cur.execute("SELECT * FROM collaborative_projects WHERE id = ?", (new_id,))
        row = cur.fetchone()

    return jsonify({"ok": True, "id": new_id, "project": _row_to_project(dict(row))})


@app.route("/api/collaborative/<int:project_id>", methods=["GET"])
def api_collaborative_get(project_id):
    """读取一个协同创作项目（必须属于当前用户）。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    with UserDB() as db:
        cur = db.conn.cursor()
        cur.execute(
            "SELECT * FROM collaborative_projects WHERE id = ? AND user_id = ?",
            (project_id, user["id"]),
        )
        row = cur.fetchone()

    if not row:
        return jsonify({"error": "项目不存在"}), 404

    return jsonify({"ok": True, "project": _row_to_project(dict(row))})


@app.route("/api/collaborative/<int:project_id>/state", methods=["POST"])
def api_collaborative_save_state(project_id):
    """持久化协同创作项目的状态。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json() or {}

    with UserDB() as db:
        cur = db.conn.cursor()
        # 先确认所有权
        cur.execute(
            "SELECT id FROM collaborative_projects WHERE id = ? AND user_id = ?",
            (project_id, user["id"]),
        )
        if not cur.fetchone():
            return jsonify({"error": "项目不存在"}), 404

        # 构建更新字段（仅更新提供的字段）
        fields = []
        params = []
        if "current_phase" in data:
            fields.append("current_phase = ?")
            params.append(data["current_phase"])
        if "title" in data:
            fields.append("title = ?")
            params.append(data["title"])
        if "topic" in data:
            fields.append("topic_json = ?")
            params.append(json.dumps(data["topic"], ensure_ascii=False))
        if "outline" in data:
            fields.append("outline_json = ?")
            params.append(json.dumps(data["outline"], ensure_ascii=False))
        if "content" in data:
            fields.append("content_json = ?")
            params.append(json.dumps(data["content"], ensure_ascii=False))

        if fields:
            fields.append("updated_at = CURRENT_TIMESTAMP")
            params.extend([project_id, user["id"]])
            cur.execute(
                f"UPDATE collaborative_projects SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                params,
            )
            db.conn.commit()

    return jsonify({"ok": True})


@app.route("/api/collaborative/<int:project_id>/save-article", methods=["POST"])
def api_collaborative_save_article(project_id):
    """将工作台的汇总内容持久化为历史文章（强制附加 AI 标识并校验）。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "标题不能为空"}), 400

    content = data.get("content", "")
    if not content:
        return jsonify({"error": "没有可保存的内容"}), 400

    topic = data.get("topic") if isinstance(data.get("topic"), dict) else {}
    outline = data.get("outline") if isinstance(data.get("outline"), dict) else {}

    # 再确认一次项目所有权（防止越权写入）
    with UserDB() as db:
        cur = db.conn.cursor()
        cur.execute(
            "SELECT id FROM collaborative_projects WHERE id = ? AND user_id = ?",
            (project_id, user["id"]),
        )
        if not cur.fetchone():
            return jsonify({"error": "项目不存在"}), 404

    try:
        article_id = save_article(
            user_id=user["id"],
            title=title,
            topic_json=topic,
            outline_json=outline,
            content=content,
        )
    except ValueError as e:
        # ai_labeler.validate_content 失败等校验错误
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True, "article_id": article_id})


@app.route("/collaborative/<int:project_id>")
def collaborative_workbench(project_id):
    """协同创作工作台页。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return render_template("collaborative/workbench.html")


@app.route("/api/collaborative/outline", methods=["POST"])
def api_collaborative_generate_outline():
    """为协同创作生成大纲（同步调用 ai_writer.generate_outline）。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json() or {}
    topic = data.get("topic", "")
    context = data.get("context") or None

    try:
        from modules.ai_writer import generate_outline
        outline = generate_outline(topic=topic, context=context, user_id=user["id"])
        return jsonify({"ok": True, "outline": outline})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/collaborative/topics", methods=["POST"])
def api_collaborative_generate_topics():
    """为协同创作生成选题候选（同步调用 ai_writer.generate_topics）。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json() or {}
    idea = data.get("idea", "")
    # count 可选，默认 5，限制在 1-10
    try:
        count = int(data.get("count", 5))
    except (TypeError, ValueError):
        count = 5
    count = max(1, min(count, 10))

    try:
        from modules.ai_writer import generate_topics
        topics = generate_topics(idea=idea, count=count, user_id=user["id"])
        return jsonify({"ok": True, "topics": topics})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/collaborative/content", methods=["POST"])
def api_collaborative_generate_content():
    """为协同创作生成正文内容（同步调用 ai_writer.generate_content）。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json() or {}
    outline = data.get("outline", {})
    section = data.get("section") or None

    try:
        from modules.ai_writer import generate_content
        result = generate_content(outline=outline, section=section, user_id=user["id"])
        return jsonify({"ok": True, "sections": result["sections"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# 协同创作 · 版本管理
# ════════════════════════════════════════════════════════════

def _require_project_owner(project_id, user):
    """校验当前用户拥有该项目，返回 True/False。"""
    with UserDB() as db:
        cur = db.conn.cursor()
        cur.execute(
            "SELECT id FROM collaborative_projects WHERE id = ? AND user_id = ?",
            (project_id, user["id"]),
        )
        return cur.fetchone() is not None


@app.route("/api/collaborative/<int:project_id>/versions", methods=["GET"])
def api_collaborative_list_versions(project_id):
    """列出项目的全部版本快照（最新在前）。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    if not _require_project_owner(project_id, user):
        return jsonify({"error": "项目不存在"}), 404

    from modules.version_manager import list_versions
    versions = list_versions(project_id)
    return jsonify({"ok": True, "versions": versions})


@app.route("/api/collaborative/<int:project_id>/versions/<int:version_id>", methods=["GET"])
def api_collaborative_get_version(project_id, version_id):
    """获取单个版本快照（必须拥有项目）。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    if not _require_project_owner(project_id, user):
        return jsonify({"error": "项目不存在"}), 404

    from modules.version_manager import get_version
    version = get_version(version_id)
    if not version or version.get("project_id") != project_id:
        return jsonify({"error": "版本不存在"}), 404
    return jsonify({"ok": True, "version": version})


@app.route("/api/collaborative/<int:project_id>/versions/compare", methods=["POST"])
def api_collaborative_compare_versions(project_id):
    """对比两个版本的内容差异。body: {"v1": <id>, "v2": <id>}。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    if not _require_project_owner(project_id, user):
        return jsonify({"error": "项目不存在"}), 404

    data = request.get_json() or {}
    v1 = data.get("v1")
    v2 = data.get("v2")

    from modules.version_manager import compare_versions
    diff = compare_versions(v1, v2)
    return jsonify({"ok": True, "diff": diff})


@app.route("/api/collaborative/<int:project_id>/versions/<int:version_id>/rollback", methods=["POST"])
def api_collaborative_rollback_version(project_id, version_id):
    """回溯到指定版本：创建一个内容相同的新手动快照。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    if not _require_project_owner(project_id, user):
        return jsonify({"error": "项目不存在"}), 404

    from modules.version_manager import rollback_to_version, get_version
    target = get_version(version_id)
    if not target or target.get("project_id") != project_id:
        return jsonify({"error": "版本不存在"}), 404

    try:
        new_id = rollback_to_version(version_id, user["id"])
    except ValueError:
        return jsonify({"error": "版本不存在"}), 404
    return jsonify({"ok": True, "id": new_id})


# ════════════════════════════════════════════════════════════
# 协同创作：历史文章（查看 / 继续编辑 / 删除）
# ════════════════════════════════════════════════════════════

@app.route("/api/collaborative/articles", methods=["GET"])
def api_collaborative_list_articles():
    """列出当前用户的历史文章（协同创作产出的 article_history）。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    try:
        articles = list_articles(user["id"])
        return jsonify({"articles": articles})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/collaborative/articles/<int:article_id>", methods=["GET"])
def api_collaborative_get_article(article_id):
    """获取单篇历史文章详情（必须属于当前用户）。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    try:
        article = get_article(article_id, user["id"])
        if not article:
            return jsonify({"error": "文章不存在"}), 404
        return jsonify({"article": article})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/collaborative/articles/<int:article_id>", methods=["DELETE"])
def api_collaborative_delete_article(article_id):
    """删除单篇历史文章（必须属于当前用户）。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    try:
        deleted = delete_article(article_id, user["id"])
        if not deleted:
            return jsonify({"error": "文章不存在"}), 404
        return jsonify({"deleted": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/collaborative/articles/<int:article_id>/continue", methods=["POST"])
def api_collaborative_continue_article(article_id):
    """基于历史文章新建协同创作项目，预填充其选题/大纲/内容。"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    try:
        article = get_article(article_id, user["id"])
        if not article:
            return jsonify({"error": "文章不存在"}), 404

        with UserDB() as db:
            cur = db.conn.cursor()
            cur.execute(
                """INSERT INTO collaborative_projects
                   (user_id, title, current_phase, topic_json, outline_json, content_json,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (
                    user["id"],
                    article["title"] or "未命名创作",
                    "content",
                    article["topic_json"],
                    article["outline_json"],
                    article["content"],
                ),
            )
            db.conn.commit()
            new_id = cur.lastrowid

        return jsonify({"project_id": new_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════
# 启动
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5678))
    print(f"\n🚀 协作写作平台管理界面启动中...")
    print(f"   打开浏览器访问：http://localhost:{port}\n")

    # 初始化默认用户
    with UserDB() as db:
        admin = db.get_user_by_username("admin")
        if not admin:
            db.create_user("admin", "123456", role="admin")
            print("✅ 默认用户已创建：admin / 123456\n")

    # 初始化系统领域分类
    from modules.user_db import init_system_domains
    init_system_domains()

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
