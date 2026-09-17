import os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from modules import user_db


@pytest.fixture
def tmp_db_path(tmp_path, monkeypatch):
    """隔离的临时数据库，重置 UserDB 单例。"""
    monkeypatch.setattr(user_db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(user_db, "_db_instance", None)
    yield tmp_path / "test.db"


@pytest.fixture
def db(tmp_db_path):
    yield user_db.UserDB()


@pytest.fixture
def app(tmp_db_path):
    """Flask test client。注意：web_app 在导入时读取 DB_PATH，故先设好 tmp_db_path。"""
    os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")
    from web_app import app as flask_app
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client
