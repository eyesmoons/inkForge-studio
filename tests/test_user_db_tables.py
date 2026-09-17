import os, sys, sqlite3, tempfile
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    # 用临时数据库隔离测试，避免污染 users.db
    from modules import user_db
    monkeypatch.setattr(user_db, "DB_PATH", tmp_path / "test.db")
    # 重置单例，强制重新建库
    monkeypatch.setattr(user_db, "_db_instance", None)
    db = user_db.UserDB()
    yield db

def test_collaborative_projects_schema(tmp_db):
    cur = tmp_db.conn.cursor()
    cur.execute("PRAGMA table_info(collaborative_projects)")
    cols = {r["name"] for r in cur.fetchall()}
    assert {"id","user_id","title","current_phase","topic_json","outline_json","content_json","created_at","updated_at"} <= cols
    cur.execute("SELECT COUNT(*) FROM collaborative_projects")
    assert cur.fetchone()[0] == 0

def test_article_history_schema(tmp_db):
    cur = tmp_db.conn.cursor()
    cur.execute("PRAGMA table_info(article_history)")
    cols = {r["name"] for r in cur.fetchall()}
    assert {"id","user_id","title","topic_json","outline_json","content_json","ai_label","created_at","updated_at"} <= cols

def test_version_snapshots_schema(tmp_db):
    cur = tmp_db.conn.cursor()
    cur.execute("PRAGMA table_info(version_snapshots)")
    cols = {r["name"] for r in cur.fetchall()}
    assert {"id","project_id","user_id","version_name","content_json","trigger_type","created_at"} <= cols

def test_ai_label_config_default_row(tmp_db):
    cur = tmp_db.conn.cursor()
    cur.execute("PRAGMA table_info(ai_label_config)")
    cols = {r["name"] for r in cur.fetchall()}
    assert {"id","label_text","updated_at","updated_by"} <= cols
    cur.execute("SELECT label_text FROM ai_label_config WHERE id = 1")
    row = cur.fetchone()
    assert row is not None
    assert "AI" in row["label_text"]
