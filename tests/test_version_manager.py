import pytest, json
from modules import version_manager

def _project(db, user_id=1):
    cur = db.conn.cursor()
    cur.execute("INSERT INTO collaborative_projects (user_id, current_phase) VALUES (?, 'topic')", (user_id,))
    db.conn.commit()
    return cur.lastrowid

def test_create_snapshot(db):
    pid = _project(db)
    vid = version_manager.create_snapshot(pid, 1, "选题确认", {"topic": "t"}, "manual")
    assert isinstance(vid, int) and vid > 0

def test_list_versions_order(db):
    pid = _project(db)
    version_manager.create_snapshot(pid, 1, "a", {"n": 1}, "auto_topic")
    version_manager.create_snapshot(pid, 1, "b", {"n": 2}, "auto_outline")
    vs = version_manager.list_versions(pid)
    assert len(vs) == 2
    assert vs[0]["created_at"] >= vs[1]["created_at"]

def test_get_version(db):
    pid = _project(db)
    vid = version_manager.create_snapshot(pid, 1, "x", {"k": "v"}, "manual")
    v = version_manager.get_version(vid)
    assert v["version_name"] == "x"
    assert json.loads(v["content_json"]) == {"k": "v"}

def test_compare_versions(db):
    pid = _project(db)
    v1 = version_manager.create_snapshot(pid, 1, "v1", {"sections": [{"id": "1", "content": "A"}]}, "auto_content")
    v2 = version_manager.create_snapshot(pid, 1, "v2", {"sections": [{"id": "1", "content": "B"}]}, "auto_content")
    diff = version_manager.compare_versions(v1, v2)
    assert "sections" in diff
    changes = diff["sections"]
    assert any(c.get("id") == "1" and c.get("old") == "A" and c.get("new") == "B" for c in changes)

def test_rollback_creates_new_snapshot(db):
    pid = _project(db)
    v1 = version_manager.create_snapshot(pid, 1, "v1", {"n": 1}, "auto_topic")
    new_id = version_manager.rollback_to_version(v1, 1)
    assert new_id != v1
    new = version_manager.get_version(new_id)
    assert json.loads(new["content_json"]) == {"n": 1}
    assert new["trigger_type"] == "manual"

def test_auto_snapshot_cap_at_20(db):
    pid = _project(db)
    for i in range(25):
        version_manager.create_snapshot(pid, 1, f"s{i}", {"n": i}, "auto_content")
    vs = version_manager.list_versions(pid)
    auto = [v for v in vs if v["trigger_type"].startswith("auto")]
    assert len(auto) == 20
    nums = [json.loads(v["content_json"])["n"] for v in auto]
    assert min(nums) == 5 and max(nums) == 24
