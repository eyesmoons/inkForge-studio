"""agent 路由集成测试"""
import json
from unittest.mock import MagicMock

from modules import coze_client


class TestCozeConfigRoute:
    def test_get_config_masked(self, app, tmp_coze_config):
        resp = app.get("/api/coze_config")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["workflow_id"] == "7569130427475705882"
        assert data["api_token_set"] is True
        # 确保不返回明文 token
        assert "api_token" not in data

    def test_get_config_empty(self, app, tmp_path, monkeypatch):
        from modules import coze_client
        monkeypatch.setattr(
            coze_client, "COZE_CONFIG_FILE", tmp_path / "none.json"
        )
        resp = app.get("/api/coze_config")
        data = resp.get_json()
        assert data["workflow_id"] == ""
        assert data["api_token_set"] is False

    def test_put_config(self, app, tmp_coze_config):
        resp = app.put(
            "/api/coze_config",
            data=json.dumps({"workflow_id": "999", "api_token": "new-token"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        # 验证持久化
        from modules.coze_client import load_coze_config
        cfg = load_coze_config()
        assert cfg["workflow_id"] == "999"
        assert cfg["api_token"] == "new-token"

    def test_put_config_missing_workflow_id(self, app, tmp_coze_config):
        resp = app.put(
            "/api/coze_config",
            data=json.dumps({"api_token": "new-token"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_config_requires_login(self, anon_app):
        resp = anon_app.get("/api/coze_config")
        assert resp.status_code == 401


class TestAgentGenerateRoute:
    def test_generate_requires_login(self, anon_app):
        resp = anon_app.post(
            "/api/agent/generate",
            data=json.dumps({"url": "http://x.com", "account_id": "demo"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_generate_missing_url(self, app, tmp_coze_config):
        resp = app.post(
            "/api/agent/generate",
            data=json.dumps({"url": "", "account_id": "demo"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_generate_coze_not_configured(self, app, tmp_path, monkeypatch):
        monkeypatch.setattr(
            coze_client, "COZE_CONFIG_FILE", tmp_path / "none.json"
        )
        resp = app.post(
            "/api/agent/generate",
            data=json.dumps({"url": "http://x.com", "account_id": "demo"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "Coze" in resp.get_json()["error"]

    def test_generate_success(self, app, tmp_coze_config, monkeypatch):
        """mock CozeWorkflowClient 验证路由返回结构"""
        import web_app as web_app_mod
        mock_client = MagicMock()
        mock_client.rewrite_article.return_value = {"title": "t", "content": "c"}
        # web_app 直接导入 CozeWorkflowClient，路由用 web_app 模块全局，需 patch 这里
        monkeypatch.setattr(
            web_app_mod, "CozeWorkflowClient",
            lambda *a, **k: mock_client,
        )
        monkeypatch.setattr(
            web_app_mod, "get_account_config",
            lambda *a, **k: {"app_id": "aid", "app_secret": "sec"},
        )

        resp = app.post(
            "/api/agent/generate",
            data=json.dumps({"url": "http://x.com", "account_id": "demo", "prompt": "p"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "t"
        assert data["content"] == "c"

    def test_generate_coze_error_returns_502(self, app, tmp_coze_config, monkeypatch):
        import web_app as web_app_mod
        mock_client = MagicMock()
        mock_client.rewrite_article.side_effect = web_app_mod.CozeAPIError("boom")
        monkeypatch.setattr(web_app_mod, "CozeWorkflowClient", lambda *a, **k: mock_client)
        monkeypatch.setattr(
            web_app_mod, "get_account_config",
            lambda *a, **k: {"app_id": "aid", "app_secret": "sec"},
        )

        resp = app.post(
            "/api/agent/generate",
            data=json.dumps({"url": "http://x.com", "account_id": "demo"}),
            content_type="application/json",
        )
        assert resp.status_code == 502


class TestAgentPushDraftRoute:
    def test_push_requires_login(self, anon_app):
        resp = anon_app.post(
            "/api/agent/push_draft",
            data=json.dumps({"title": "t", "content": "c", "account_id": "demo"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_push_missing_title(self, app, tmp_coze_config):
        resp = app.post(
            "/api/agent/push_draft",
            data=json.dumps({"title": "", "content": "c", "account_id": "demo"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_push_success(self, app, tmp_coze_config, monkeypatch):
        import web_app as web_app_mod
        mock_publisher = MagicMock()
        mock_publisher.create_draft_only.return_value = {
            "success": True, "media_id": "mid-123", "msg": "ok",
        }
        monkeypatch.setattr(web_app_mod, "WeChatPublisher", lambda *a, **k: mock_publisher)
        monkeypatch.setattr(
            web_app_mod, "get_account_config",
            lambda *a, **k: {"app_id": "aid", "app_secret": "sec", "author": "作者"},
        )

        resp = app.post(
            "/api/agent/push_draft",
            data=json.dumps({"title": "标题", "content": "正文", "account_id": "demo"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["media_id"] == "mid-123"

    def test_push_wx_error_returns_500(self, app, tmp_coze_config, monkeypatch):
        import web_app as web_app_mod
        from modules.wx_publisher import WeChatAPIError
        mock_publisher = MagicMock()
        mock_publisher.create_draft_only.side_effect = WeChatAPIError("wx boom")
        monkeypatch.setattr(web_app_mod, "WeChatPublisher", lambda *a, **k: mock_publisher)
        monkeypatch.setattr(
            web_app_mod, "get_account_config",
            lambda *a, **k: {"app_id": "aid", "app_secret": "sec"},
        )

        resp = app.post(
            "/api/agent/push_draft",
            data=json.dumps({"title": "t", "content": "c", "account_id": "demo"}),
            content_type="application/json",
        )
        assert resp.status_code == 500