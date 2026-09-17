"""
tests/test_collaborative_history_frontend.py
协同创作历史文章前端 API 的回归测试。

测试策略：通过注册流程创建真实登录用户，以 X-Session-Id 头驱动请求；
历史文章直接通过 modules.article_history.save_article 写入。
"""
import json
import uuid

import pytest

from modules import article_history


def _register_user(app, username=None, password="password123"):
    """通过注册流程创建用户并返回 (session_id, user_id)。"""
    username = username or f"user_{uuid.uuid4().hex[:8]}"
    resp = app.post(
        "/api/auth/register",
        json={"username": username, "password": password, "email": ""},
    )
    data = resp.get_json()
    assert resp.status_code == 200, data
    return data["session_id"], data.get("user", {}).get("id")


def _seed_article(user_id, title="历史文章"):
    """写入一篇带 AI 标识的历史文章，返回 article id。"""
    return article_history.save_article(
        user_id=user_id,
        title=title,
        topic_json={"title": "测试选题"},
        outline_json={"sections": []},
        content="这是一篇测试正文。",
    )


def test_list_articles_requires_auth(app):
    """未登录 GET 历史文章列表 → 401。"""
    resp = app.get("/api/collaborative/articles")
    assert resp.status_code == 401
    assert resp.get_json().get("error") == "请先登录"


def test_list_articles_returns_owned(app):
    """登录用户仅能看到自己的历史文章。"""
    session_a, user_a = _register_user(app, username="hist_owner_a")
    session_b, user_b = _register_user(app, username="hist_owner_b")

    aid = _seed_article(user_a, title="A 的文章")

    # 所有者 A 能看到
    resp_a = app.get(
        "/api/collaborative/articles",
        headers={"X-Session-Id": session_a},
    )
    data_a = resp_a.get_json()
    assert resp_a.status_code == 200, data_a
    articles = data_a["articles"]
    assert len(articles) == 1
    assert articles[0]["id"] == aid
    assert articles[0]["title"] == "A 的文章"
    # 返回内容应包含 AI 标识
    assert articles[0].get("ai_label")

    # 用户 B 看不到 A 的文章
    resp_b = app.get(
        "/api/collaborative/articles",
        headers={"X-Session-Id": session_b},
    )
    assert resp_b.status_code == 200
    assert resp_b.get_json()["articles"] == []


def test_get_article_ownership(app):
    """所有者获取文章 → 200；非所有者 → 404。"""
    session_a, user_a = _register_user(app, username="hist_get_a")
    session_b, _ = _register_user(app, username="hist_get_b")
    aid = _seed_article(user_a, title="私有文章")

    resp_ok = app.get(
        f"/api/collaborative/articles/{aid}",
        headers={"X-Session-Id": session_a},
    )
    assert resp_ok.status_code == 200
    article = resp_ok.get_json()["article"]
    assert article["id"] == aid
    assert article["title"] == "私有文章"
    # 内容应含 AI 标识
    assert article.get("ai_label") and article["ai_label"] in article["content"]

    resp_other = app.get(
        f"/api/collaborative/articles/{aid}",
        headers={"X-Session-Id": session_b},
    )
    assert resp_other.status_code == 404
    assert resp_other.get_json().get("error") == "文章不存在"


def test_continue_creates_prefilled_project(app):
    """基于历史文章继续编辑 → 新建预填充协同创作项目；非所有者 → 404。"""
    session_a, user_a = _register_user(app, username="hist_cont_a")
    session_b, _ = _register_user(app, username="hist_cont_b")

    aid = article_history.save_article(
        user_id=user_a,
        title="可继续的文章",
        topic_json={"title": "选题 X"},
        outline_json={"sections": [{"id": "s1", "title": "引言"}]},
        content="正文内容",
    )

    resp = app.post(
        f"/api/collaborative/articles/{aid}/continue",
        headers={"X-Session-Id": session_a},
    )
    data = resp.get_json()
    assert resp.status_code == 200, data
    assert "project_id" in data and data["project_id"]
    project_id = data["project_id"]

    # 验证新项目：属于当前用户、content 阶段、预填充了文章内容
    from modules.user_db import UserDB

    with UserDB() as db:
        cur = db.conn.cursor()
        cur.execute(
            "SELECT user_id, title, current_phase, topic_json, outline_json, content_json "
            "FROM collaborative_projects WHERE id = ?",
            (project_id,),
        )
        row = cur.fetchone()
    assert row is not None
    assert row["user_id"] == user_a
    assert row["title"] == "可继续的文章"
    assert row["current_phase"] == "content"
    # 预填充的 JSON 列应可被解析为原始结构
    assert json.loads(row["topic_json"]) == {"title": "选题 X"}
    assert json.loads(row["outline_json"]) == {"sections": [{"id": "s1", "title": "引言"}]}
    # 内容应包含原正文（含 AI 标识）
    assert "正文内容" in row["content_json"]

    # 非所有者继续编辑 → 404
    resp_other = app.post(
        f"/api/collaborative/articles/{aid}/continue",
        headers={"X-Session-Id": session_b},
    )
    assert resp_other.status_code == 404


def test_delete_article(app):
    """所有者删除 → 200；二次删除 → 404；非所有者 → 404。"""
    session_a, user_a = _register_user(app, username="hist_del_a")
    session_b, _ = _register_user(app, username="hist_del_b")
    aid = _seed_article(user_a, title="待删除")

    resp_del = app.delete(
        f"/api/collaborative/articles/{aid}",
        headers={"X-Session-Id": session_a},
    )
    assert resp_del.status_code == 200
    assert resp_del.get_json().get("deleted") is True

    # 二次删除 → 已不存在 → 404
    resp_again = app.delete(
        f"/api/collaborative/articles/{aid}",
        headers={"X-Session-Id": session_a},
    )
    assert resp_again.status_code == 404

    # 非所有者删除他人文章 → 404
    aid2 = _seed_article(user_a, title="另一篇")
    resp_other = app.delete(
        f"/api/collaborative/articles/{aid2}",
        headers={"X-Session-Id": session_b},
    )
    assert resp_other.status_code == 404
