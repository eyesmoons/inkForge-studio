"""
tests/test_collaborative_topics.py
协同创作选题生成 API 的回归测试。
"""
import json
from unittest.mock import patch


def _register_user(app):
    """注册一个测试用户并返回 session_id。"""
    resp = app.post(
        "/api/auth/register",
        json={"username": "topic_tester", "password": "testpass123", "email": "t@e.com"},
    )
    data = resp.get_json()
    return data["session_id"]


def test_generate_topics_requires_auth(app):
    """未登录时 POST /api/collaborative/topics 应返回 401。"""
    resp = app.post(
        "/api/collaborative/topics",
        json={"idea": "Python 异步编程"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "请先登录"


def test_generate_topics_returns_topics(app):
    """已登录用户提交 idea 后应返回 ok=True 且 topics 为非空列表。"""
    session_id = _register_user(app)
    headers = {"X-Session-Id": session_id}

    fake_topics = [
        {"title": "t1", "description": "d1"},
        {"title": "t2", "description": "d2"},
    ]
    with patch("modules.ai_writer.generate_topics", return_value=fake_topics) as mock_gen:
        resp = app.post(
            "/api/collaborative/topics",
            json={"idea": "Python 异步编程"},
            headers=headers,
        )
        # 断言 mock 被以正确的 idea 和 count 调用
        mock_gen.assert_called_once()
        _, kwargs = mock_gen.call_args
        assert kwargs.get("idea") == "Python 异步编程"
        assert isinstance(kwargs.get("count"), int)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert isinstance(data["topics"], list)
    assert len(data["topics"]) > 0
    assert "title" in data["topics"][0]


def test_generate_topics_count_default(app):
    """不传 count 时接口仍能正常工作（使用默认值）。"""
    session_id = _register_user(app)
    headers = {"X-Session-Id": session_id}

    fake_topics = [{"title": "t1", "description": "d1"}]
    with patch("modules.ai_writer.generate_topics", return_value=fake_topics) as mock_gen:
        resp = app.post(
            "/api/collaborative/topics",
            json={"idea": "Python 异步编程"},
            headers=headers,
        )
        mock_gen.assert_called_once()
        _, kwargs = mock_gen.call_args
        # 默认 count 应为 5
        assert kwargs.get("count") == 5

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["topics"] == fake_topics
