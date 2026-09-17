import json
from modules.user_db import get_db


def create_snapshot(project_id, user_id, version_name, content_json, trigger_type) -> int:
    """创建版本快照。返回新快照 ID。"""
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            """INSERT INTO version_snapshots (project_id, user_id, version_name, content_json, trigger_type)
               VALUES (?, ?, ?, ?, ?)""",
            (project_id, user_id, version_name, json.dumps(content_json, ensure_ascii=False), trigger_type),
        )
        db.conn.commit()
        vid = cur.lastrowid
    # 自动快照需要执行上限裁剪
    if trigger_type.startswith("auto"):
        _cap_auto_snapshots(project_id, cap=20)
    return vid


def list_versions(project_id) -> list:
    """列出项目的所有版本快照，按 created_at DESC, id DESC 排序（最新在前）。"""
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            """SELECT id, project_id, user_id, version_name, content_json, trigger_type, created_at
               FROM version_snapshots
               WHERE project_id = ?
               ORDER BY created_at DESC, id DESC""",
            (project_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_version(version_id) -> dict:
    """获取单个版本快照。"""
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            """SELECT id, project_id, user_id, version_name, content_json, trigger_type, created_at
               FROM version_snapshots WHERE id = ?""",
            (version_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def compare_versions(v1_id, v2_id) -> dict:
    """比较两个版本快照的内容差异。返回包含 sections 差异及顶层键差异的字典。"""
    ver1 = get_version(v1_id)
    ver2 = get_version(v2_id)
    c1 = json.loads(ver1["content_json"]) if ver1 else {}
    c2 = json.loads(ver2["content_json"]) if ver2 else {}
    return _diff_content(c1, c2)


def rollback_to_version(version_id, user_id) -> int:
    """回溯到指定版本：创建一个内容相同的新手动快照。返回新快照 ID。"""
    target = get_version(version_id)
    if target is None:
        raise ValueError(f"version {version_id} not found")
    name = target["version_name"] or f"id={version_id}"
    return create_snapshot(
        project_id=target["project_id"],
        user_id=user_id,
        version_name=f"回溯自 {name}",
        content_json=json.loads(target["content_json"]),
        trigger_type="manual",
    )


def _cap_auto_snapshots(project_id, cap=20) -> None:
    """保留项目最新的 cap 条自动快照，删除更早的。"""
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            """DELETE FROM version_snapshots
               WHERE project_id = ? AND trigger_type LIKE 'auto%'
                 AND id NOT IN (
                     SELECT id FROM version_snapshots
                     WHERE project_id = ? AND trigger_type LIKE 'auto%'
                     ORDER BY created_at DESC, id DESC
                     LIMIT ?
                 )""",
            (project_id, project_id, cap),
        )
        db.conn.commit()


def _diff_content(c1, c2) -> dict:
    """对比两个内容字典的差异。

    - 若某键对应的值为 section 数组（含 "id" 的字典列表），按 id 匹配，列出 {id, old, new} 变更。
    - 顶层标量/其他键的差异以 {key, old, new} 形式放入 "changes"。
    """
    diff = {}
    changes = []
    keys = set(c1.keys()) | set(c2.keys())
    for key in keys:
        v1 = c1.get(key)
        v2 = c2.get(key)
        # section 数组差异（含 "id" 的字典列表）：按 id 匹配，old/new 取 content 值
        if isinstance(v1, list) and isinstance(v2, list) and v1 and isinstance(v1[0], dict) and "id" in v1[0]:
            by_id = {item["id"]: item for item in v1 if isinstance(item, dict) and "id" in item}
            section_changes = []
            for item in v2:
                if not isinstance(item, dict) or "id" not in item:
                    continue
                iid = item["id"]
                old_item = by_id.get(iid)
                new_content = item.get("content", item)
                if old_item is None:
                    section_changes.append({"id": iid, "old": None, "new": new_content})
                else:
                    old_content = old_item.get("content", old_item)
                    if old_content != new_content:
                        section_changes.append({"id": iid, "old": old_content, "new": new_content})
            # 处理被删除的 section
            new_ids = {item["id"] for item in v2 if isinstance(item, dict) and "id" in item}
            for item in v1:
                if isinstance(item, dict) and "id" in item and item["id"] not in new_ids:
                    section_changes.append({"id": item["id"], "old": item.get("content", item), "new": None})
            if section_changes:
                diff[key] = section_changes
        else:
            if v1 != v2:
                changes.append({"key": key, "old": v1, "new": v2})
    if changes:
        diff["changes"] = changes
    return diff
