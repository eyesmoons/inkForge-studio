"""
tests/test_image_generator.py
AI 配图（image_generator + /api/material_library/generate）回归测试。
"""
import json
import uuid
from unittest import mock

import pytest

from modules import image_generator


def _register_user(app, username=None, password="password123"):
    username = username or f"user_{uuid.uuid4().hex[:8]}"
    resp = app.post(
        "/api/auth/register",
        json={"username": username, "password": password, "email": ""},
    )
    data = resp.get_json()
    assert resp.status_code == 200, data
    return data["session_id"], data.get("user", {}).get("id")


def _set_image_model(user_id, api_key="sk-test", api_base="https://api.example.com/v1", model_name="fake-image"):
    """写入一条图像生成模型配置。"""
    from modules.user_db import UserDB
    with UserDB() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            "INSERT INTO ai_models (user_id, name, provider, model_name, api_key, api_base, is_default, is_image_model) VALUES (?,?,?,?,?,?,?,?)",
            (user_id, "测试图像模型", "other", model_name, api_key, api_base, 0, 1),
        )
        db.conn.commit()
        return cur.lastrowid


# ── 模块级行为 ──────────────────────────────────────────────

def test_generate_empty_prompt():
    """空 prompt → 本地校验失败，不发请求。"""
    result = image_generator.generate_image("   ", user_id=1)
    assert result["ok"] is False
    assert "描述" in result["error"]


def test_generate_no_image_model():
    """用户未配置图像生成模型 → 明确提示。"""
    result = image_generator.generate_image("一只猫", user_id=999999)
    assert result["ok"] is False
    assert "尚未配置" in result["error"]


def test_generate_success_mocked(tmp_path, app):
    """mock 图片 API 返回 url → 下载并保存到本地素材目录，返回 url。"""
    # 配置图像模型
    sid, uid = _register_user(app, username="img_user")
    _set_image_model(uid)

    fake_url = "https://api.example.com/out.png"

    # 把「调图片 API」与「下载到本地」分开：mock 返回 url，并 stub 下载直接落盘
    def fake_download(url, dest_path):
        dest_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
        return True

    with mock.patch.object(image_generator, "MATERIAL_DIR", tmp_path), \
         mock.patch("modules.image_generator.requests.post") as mock_post, \
         mock.patch("modules.image_generator._download_image", side_effect=fake_download):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"data": [{"url": fake_url}]}

        result = image_generator.generate_image("一只猫在月光下", user_id=uid)

    assert result["ok"] is True, result
    assert result["url"].startswith("/api/material_library/image/")
    assert result["url"].endswith(".png")
    # 文件确实落到 tmp_path
    assert any(tmp_path.iterdir())


# ── API 级行为 ──────────────────────────────────────────────

def test_generate_api_requires_auth(app):
    """未登录调用生成接口 → 401。"""
    resp = app.post("/api/material_library/generate", json={"prompt": "一只猫"})
    assert resp.status_code == 401


def test_generate_api_empty_prompt(app):
    """空 prompt → 400。"""
    sid, _ = _register_user(app, username="img_empty")
    resp = app.post(
        "/api/material_library/generate",
        json={"prompt": "   "},
        headers={"X-Session-Id": sid},
    )
    assert resp.status_code == 400
    assert "描述" in resp.get_json()["error"]


def test_generate_api_no_model(app):
    """已登录但无图像模型 → 400 + 明确提示。"""
    sid, _ = _register_user(app, username="img_nomod")
    resp = app.post(
        "/api/material_library/generate",
        json={"prompt": "一只猫"},
        headers={"X-Session-Id": sid},
    )
    assert resp.status_code == 400
    assert "尚未配置" in resp.get_json()["error"]


def test_generate_api_success_mocked(app, tmp_path):
    """mock 成功 → 200 + url。"""
    sid, uid = _register_user(app, username="img_ok")
    _set_image_model(uid)

    fake_url = "https://api.example.com/ok.png"

    def fake_download(url, dest_path):
        dest_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
        return True

    with mock.patch.object(image_generator, "MATERIAL_DIR", tmp_path), \
         mock.patch("modules.image_generator.requests.post") as mock_post, \
         mock.patch("modules.image_generator._download_image", side_effect=fake_download):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"data": [{"url": fake_url}]}

        resp = app.post(
            "/api/material_library/generate",
            json={"prompt": "夕阳下的灯塔"},
            headers={"X-Session-Id": sid},
        )

    data = resp.get_json()
    assert resp.status_code == 200, data
    assert data["ok"] is True
    assert data["url"].startswith("/api/material_library/image/")
