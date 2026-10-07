"""pytest 共享 fixture"""
import json
import sys
import pytest
from pathlib import Path

# 确保可导入项目模块
sys.path.insert(0, str(Path(__file__).parent.parent))

import web_app as web_app_mod
from modules import coze_client
import modules.user_db as user_db_mod


@pytest.fixture
def tmp_coze_config(tmp_path, monkeypatch):
    """创建临时 coze_config.json 并让 coze_client 指向它"""
    cfg = {"workflow_id": "7569130427475705882", "api_token": "test-token-xxx"}
    config_file = tmp_path / "coze_config.json"
    config_file.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(coze_client, "COZE_CONFIG_FILE", config_file)
    return config_file


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """将 user_db 数据库指向临时文件（_init_db 自动创建 admin，id=1），隔离真实 .cache/users.db"""
    db_file = tmp_path / "test_users.db"
    monkeypatch.setattr(user_db_mod, "DB_PATH", db_file)
    # 实例化触发 _init_db，自动创建 admin 用户
    with user_db_mod.UserDB() as db:
        db.get_user_by_username("admin")
    return db_file


@pytest.fixture
def app(isolated_db):
    """已认证的 Flask 测试客户端（通过真实 session_id cookie 机制）"""
    web_app_mod.app.config["TESTING"] = True
    with user_db_mod.UserDB() as db:
        session_id = db.create_session(1)
    with web_app_mod.app.test_client() as client:
        client.set_cookie("session_id", session_id)
        yield client


@pytest.fixture
def anon_app(isolated_db):
    """未认证的 Flask 测试客户端"""
    web_app_mod.app.config["TESTING"] = True
    with web_app_mod.app.test_client() as client:
        yield client