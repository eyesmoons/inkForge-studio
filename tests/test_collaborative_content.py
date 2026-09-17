"""
tests/test_collaborative_content.py
内容生成 API 的回归测试（Task 11）。
"""
import json
from unittest.mock import patch


def _register_user(app):
    """注册一个测试用户并返回 session_id。"""
    resp = app.post(
        "/api/auth/register",
        json={"username": "content_tester", "password": "testpass123", "email": "c@e.com"},
    )
    data = resp.get_json()
    return data["session_id"]


def test_generate_content_requires_auth(app):
    """未登录时 POST /api/collaborative/content 应返回 401。"""
    resp = app.post(
        "/api/collaborative/content",
        json={"outline": {"sections": [{"id": "s1", "title": "介绍", "points": [], "children": []}]}},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "请先登录"


def test_generate_content_all(app):
    """已登录用户提交 outline（不指定 section）应生成全部章节内容。"""
    session_id = _register_user(app)
    headers = {"X-Session-Id": session_id}

    fake_result = {
        "sections": [
            {"id": "s1", "title": "介绍", "content": "这是介绍正文", "status": "generated"}
        ]
    }
    outline = {"sections": [{"id": "s1", "title": "介绍", "points": [], "children": []}]}

    with patch("modules.ai_writer.generate_content", return_value=fake_result) as mock_gen:
        resp = app.post(
            "/api/collaborative/content",
            json={"outline": outline},
            headers=headers,
        )
        mock_gen.assert_called_once()
        _, kwargs = mock_gen.call_args
        # 未指定 section 时，应以 section=None 调用
        assert kwargs.get("section") is None
        assert kwargs.get("outline") == outline

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert isinstance(data["sections"], list)
    assert len(data["sections"]) > 0
    assert "content" in data["sections"][0]


def test_generate_content_single_section(app):
    """指定 section 时，mock 应接收到 section=='s1'（以及 outline）。"""
    session_id = _register_user(app)
    headers = {"X-Session-Id": session_id}

    fake_result = {
        "sections": [
            {"id": "s1", "title": "介绍", "content": "这是介绍正文", "status": "generated"}
        ]
    }
    outline = {"sections": [{"id": "s1", "title": "介绍", "points": [], "children": []}]}

    with patch("modules.ai_writer.generate_content", return_value=fake_result) as mock_gen:
        resp = app.post(
            "/api/collaborative/content",
            json={"outline": outline, "section": "s1"},
            headers=headers,
        )
        mock_gen.assert_called_once()
        _, kwargs = mock_gen.call_args
        assert kwargs.get("section") == "s1"
        assert kwargs.get("outline") == outline

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["sections"][0]["id"] == "s1"
