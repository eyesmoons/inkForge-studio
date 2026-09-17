"""
tests/test_collaborative_versions.py
协同创作版本管理 API 的回归测试。

测试策略：通过注册流程创建真实登录用户，以 X-Session-Id 头驱动请求；
快照直接通过 modules.version_manager.create_snapshot 创建。
"""
import uuid

import pytest

from modules.version_manager import create_snapshot


def _register_user(app, username=None, password="password123"):
    """通过注册流程创建用户并返回 session_id。"""
    username = username or f"user_{uuid.uuid4().hex[:8]}"
    resp = app.post(
        "/api/auth/register",
        json={"username": username, "password": password, "email": ""},
    )
    data = resp.get_json()
    assert resp.status_code == 200, data
    return data["session_id"], data.get("user", {}).get("id")


def _create_project(app, session_id):
    """创建一个协同创作项目，返回 project_id。"""
    resp = app.post(
        "/api/collaborative/create",
        json={"title": "版本测试项目"},
        headers={"X-Session-Id": session_id},
    )
    data = resp.get_json()
    assert resp.status_code == 200, data
    return data["id"]


def test_list_versions_requires_auth(app):
    """未登录 GET 版本列表 → 401。"""
    resp = app.get("/api/collaborative/1/versions")
    assert resp.status_code == 401
    assert resp.get_json().get("error") == "请先登录"


def test_list_versions_ownership(app):
    """用户 A 创建项目+快照，用户 B GET A 的版本 → 404。"""
    session_a, user_a = _register_user(app, username="ver_owner_a")
    session_b, _ = _register_user(app, username="ver_viewer_b")

    project_id = _create_project(app, session_a)
    create_snapshot(project_id, user_a, "初始版本", {"topic": {"title": "测试"}}, "manual")

    resp_b = app.get(
        f"/api/collaborative/{project_id}/versions",
        headers={"X-Session-Id": session_b},
    )
    assert resp_b.status_code == 404
    assert resp_b.get_json().get("error") == "项目不存在"


def test_list_versions_returns_list(app):
    """登录用户创建项目 + 2 个快照，GET → 200，ok，数量为 2，最新在前。"""
    session_id, user_id = _register_user(app, username="ver_list_user")
    project_id = _create_project(app, session_id)

    create_snapshot(project_id, user_id, "版本一", {"topic": {"title": "一"}}, "manual")
    create_snapshot(project_id, user_id, "版本二", {"topic": {"title": "二"}}, "manual")

    resp = app.get(
        f"/api/collaborative/{project_id}/versions",
        headers={"X-Session-Id": session_id},
    )
    data = resp.get_json()
    assert resp.status_code == 200, data
    assert data.get("ok") is True
    assert len(data["versions"]) == 2
    # 最新在前：第二个创建的快照（版本二）应排在第一
    assert data["versions"][0]["version_name"] == "版本二"
    assert data["versions"][1]["version_name"] == "版本一"


def test_rollback_creates_new_version(app):
    """创建项目 + 快照，POST 回溯 → 200，ok，返回新 id；列表现在有 2 条。"""
    session_id, user_id = _register_user(app, username="ver_rollback_user")
    project_id = _create_project(app, session_id)

    vid = create_snapshot(project_id, user_id, "初始版本", {"topic": {"title": "原始"}}, "manual")

    resp = app.post(
        f"/api/collaborative/{project_id}/versions/{vid}/rollback",
        headers={"X-Session-Id": session_id},
    )
    data = resp.get_json()
    assert resp.status_code == 200, data
    assert data.get("ok") is True
    assert "id" in data and data["id"]

    # 列表现在应有 2 条（原始快照 + 回溯产生的新快照）
    resp_list = app.get(
        f"/api/collaborative/{project_id}/versions",
        headers={"X-Session-Id": session_id},
    )
    list_data = resp_list.get_json()
    assert resp_list.status_code == 200, list_data
    assert len(list_data["versions"]) == 2
