"""
tests/test_collaborative_outline.py
大纲生成 API 的回归测试（Task 10）。
"""
import json
from unittest.mock import patch


def _register_user(app):
    """注册一个测试用户并返回 session_id。"""
    resp = app.post(
        "/api/auth/register",
        json={"username": "outline_tester", "password": "testpass123", "email": "o@e.com"},
    )
    data = resp.get_json()
    return data["session_id"]


def test_generate_outline_requires_auth(app):
    """未登录时 POST /api/collaborative/outline 应返回 401。"""
    resp = app.post(
        "/api/collaborative/outline",
        json={"topic": "Python 异步编程"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "请先登录"


def test_generate_outline_returns_outline(app):
    """已登录用户提交 topic 后应返回 ok=True 且 outline.sections 为非空列表。"""
    session_id = _register_user(app)
    headers = {"X-Session-Id": session_id}

    fake_outline = {
        "sections": [
            {"id": "s1", "title": "介绍", "points": ["要点一"], "children": []},
        ]
    }
    with patch("modules.ai_writer.generate_outline", return_value=fake_outline) as mock_gen:
        resp = app.post(
            "/api/collaborative/outline",
            json={"topic": "Python 异步编程"},
            headers=headers,
        )
        mock_gen.assert_called_once()
        _, kwargs = mock_gen.call_args
        assert kwargs.get("topic") == "Python 异步编程"

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert isinstance(data["outline"], dict)
    assert isinstance(data["outline"]["sections"], list)
    assert len(data["outline"]["sections"]) > 0


def test_generate_outline_passes_context(app):
    """提交 topic + context 时，mock 应同时接收到这两个参数。"""
    session_id = _register_user(app)
    headers = {"X-Session-Id": session_id}

    fake_outline = {
        "sections": [{"id": "s1", "title": "介绍", "points": [], "children": []}]
    }
    with patch("modules.ai_writer.generate_outline", return_value=fake_outline) as mock_gen:
        resp = app.post(
            "/api/collaborative/outline",
            json={"topic": "Python 异步编程", "context": "面向初学者"},
            headers=headers,
        )
        mock_gen.assert_called_once()
        _, kwargs = mock_gen.call_args
        assert kwargs.get("topic") == "Python 异步编程"
        assert kwargs.get("context") == "面向初学者"

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
