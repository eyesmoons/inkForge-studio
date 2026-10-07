"""modules/coze_client.py 单元测试"""
import json
import pytest
from unittest.mock import patch, MagicMock
from modules.coze_client import (
    CozeAPIError,
    CozeWorkflowClient,
    load_coze_config,
    save_coze_config,
)


class TestLoadCozeConfig:
    def test_load_existing_config(self, tmp_coze_config):
        data = load_coze_config()
        assert data["workflow_id"] == "7569130427475705882"
        assert data["api_token"] == "test-token-xxx"

    def test_load_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "modules.coze_client.COZE_CONFIG_FILE",
            tmp_path / "nonexistent.json",
        )
        assert load_coze_config() == {}


class TestSaveCozeConfig:
    def test_save_roundtrip(self, tmp_path, monkeypatch):
        config_file = tmp_path / "coze_config.json"
        monkeypatch.setattr("modules.coze_client.COZE_CONFIG_FILE", config_file)
        save_coze_config({"workflow_id": "123", "api_token": "abc"})
        loaded = load_coze_config()
        assert loaded["workflow_id"] == "123"
        assert loaded["api_token"] == "abc"


class TestCozeWorkflowClientInit:
    def test_missing_workflow_id_raises(self):
        with pytest.raises(CozeAPIError, match="workflow_id"):
            CozeWorkflowClient(workflow_id="", api_token="tok")

    def test_missing_api_token_raises(self):
        with pytest.raises(CozeAPIError, match="api_token"):
            CozeWorkflowClient(workflow_id="wid", api_token="")

    def test_valid_init(self):
        # 不实际调用 API，仅验证构造不抛错
        client = CozeWorkflowClient(workflow_id="wid", api_token="tok")
        assert client.workflow_id == "wid"


class TestRewriteArticle:
    def test_successful_parse(self):
        client = CozeWorkflowClient(workflow_id="wid", api_token="tok")
        # mock 内部 _client
        mock_result = MagicMock()
        mock_result.data = json.dumps({"title": "测试标题", "content": "测试正文"})
        client._client = MagicMock()
        client._client.workflows.runs.create.return_value = mock_result

        result = client.rewrite_article("http://x.com", "aid", "sec", "不要抄袭")
        assert result == {"title": "测试标题", "content": "测试正文"}

    def test_empty_data_raises(self):
        client = CozeWorkflowClient(workflow_id="wid", api_token="tok")
        mock_result = MagicMock()
        mock_result.data = ""
        client._client = MagicMock()
        client._client.workflows.runs.create.return_value = mock_result

        with pytest.raises(CozeAPIError, match="返回为空"):
            client.rewrite_article("http://x.com", "aid", "sec", "p")

    def test_invalid_json_raises(self):
        client = CozeWorkflowClient(workflow_id="wid", api_token="tok")
        mock_result = MagicMock()
        mock_result.data = "not-json-{{{"
        client._client = MagicMock()
        client._client.workflows.runs.create.return_value = mock_result

        with pytest.raises(CozeAPIError, match="解析失败"):
            client.rewrite_article("http://x.com", "aid", "sec", "p")

    def test_api_exception_wrapped(self):
        client = CozeWorkflowClient(workflow_id="wid", api_token="tok")
        client._client = MagicMock()
        client._client.workflows.runs.create.side_effect = RuntimeError("boom")

        with pytest.raises(CozeAPIError, match="调用失败"):
            client.rewrite_article("http://x.com", "aid", "sec", "p")
