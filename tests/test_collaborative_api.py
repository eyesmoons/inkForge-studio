"""
tests/test_collaborative_api.py
协同创作路由与状态持久化 API 的回归测试。

测试策略：通过现有 api_register 流程创建真实登录用户，
再以 X-Session-Id 头驱动请求。
"""
import json
import uuid

import pytest


def _register_user(app, username=None, password="password123"):
    """通过注册流程创建用户并返回 session_id。"""
    username = username or f"user_{uuid.uuid4().hex[:8]}"
    resp = app.post(
        "/api/auth/register",
        json={"username": username, "password": password, "email": ""},
    )
    data = resp.get_json()
    assert resp.status_code == 200, data
    return data["session_id"]


def test_create_requires_auth(app):
    """未登录创建项目 → 401。"""
    resp = app.post("/api/collaborative/create", json={"title": "测试"})
    assert resp.status_code == 401
    assert resp.get_json().get("error") == "请先登录"


def test_create_project(app):
    """登录后创建项目 → 200，且可通过 GET 读回。"""
    session_id = _register_user(app)

    resp = app.post(
        "/api/collaborative/create",
        json={"title": "我的协同创作"},
        headers={"X-Session-Id": session_id},
    )
    data = resp.get_json()
    assert resp.status_code == 200, data
    assert data.get("ok") is True
    assert "id" in data and data["id"]
    assert data["project"]["title"] == "我的协同创作"
    assert data["project"]["current_phase"] == "topic"
    project_id = data["id"]

    # 读回
    resp2 = app.get(
        f"/api/collaborative/{project_id}",
        headers={"X-Session-Id": session_id},
    )
    data2 = resp2.get_json()
    assert resp2.status_code == 200, data2
    assert data2["project"]["title"] == "我的协同创作"
    assert data2["project"]["current_phase"] == "topic"


def test_get_state_ownership(app):
    """用户 A 创建的项目，用户 B 读取 → 404。"""
    session_a = _register_user(app, username="owner_a")
    session_b = _register_user(app, username="viewer_b")

    resp = app.post(
        "/api/collaborative/create",
        json={"title": "私有项目"},
        headers={"X-Session-Id": session_a},
    )
    project_id = resp.get_json()["id"]

    resp_b = app.get(
        f"/api/collaborative/{project_id}",
        headers={"X-Session-Id": session_b},
    )
    assert resp_b.status_code == 404
    assert resp_b.get_json().get("error") == "项目不存在"


def test_save_and_restore_state(app):
    """写入 phase/topic/outline/content，读回后 JSON 字段正确解析。"""
    session_id = _register_user(app, username="saver")

    resp = app.post(
        "/api/collaborative/create",
        json={"title": "持久化测试"},
        headers={"X-Session-Id": session_id},
    )
    project_id = resp.get_json()["id"]

    topic = {"title": "AI 手机", "keywords": ["AI", "手机"]}
    outline = {"sections": [{"id": "s1", "title": "引言"}]}
    content = [{"id": "s1", "content": "正文内容"}]

    resp_save = app.post(
        f"/api/collaborative/{project_id}/state",
        json={
            "current_phase": "outline",
            "topic": topic,
            "outline": outline,
            "content": content,
            "title": "更新后的标题",
        },
        headers={"X-Session-Id": session_id},
    )
    assert resp_save.status_code == 200, resp_save.get_json()
    assert resp_save.get_json().get("ok") is True

    resp_get = app.get(
        f"/api/collaborative/{project_id}",
        headers={"X-Session-Id": session_id},
    )
    data = resp_get.get_json()
    assert resp_get.status_code == 200, data
    proj = data["project"]
    assert proj["current_phase"] == "outline"
    assert proj["title"] == "更新后的标题"
    # JSON 列应被解析回对象
    assert proj["topic"] == topic
    assert proj["outline"] == outline
    assert proj["content"] == content


def test_workbench_requires_auth(app):
    """未登录访问工作台页 → 302 重定向到 /login.html。"""
    resp = app.get("/collaborative/1")
    assert resp.status_code == 302
    assert "/login.html" in resp.headers.get("Location", "")
