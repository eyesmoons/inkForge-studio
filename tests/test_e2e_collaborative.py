"""
tests/test_e2e_collaborative.py
协同创作端到端集成测试（设计文档 §8.4 的 5 个关键场景 12.1–12.5）。

策略：monkeypatch web_app.get_current_user 固定为 admin 用户（id=1），
ai_writer 的 LLM 调用以 unittest.mock.patch 替换为确定性返回。
版本快照通过 modules.version_manager.create_snapshot 直接创建
（当前实现无 POST 创建快照路由，见任务说明）。
"""
import json
import os
from pathlib import Path
from unittest.mock import patch

import web_app
from modules import article_history as ah
from modules.ai_labeler import DEFAULT_LABEL, set_label_text
from modules.version_manager import create_snapshot

ROOT = Path(__file__).resolve().parent.parent

TOPICS = [{"title": "t1", "description": "d1"}]
OUTLINE = {"sections": [{"id": "s1", "title": "章节", "points": ["p"], "children": []}]}
CONTENT = {"sections": [{"id": "s1", "title": "章节", "content": "正文", "status": "generated"}]}
# save-article 路由对 content 做字符串操作，故此处为正文串（标识由 save_article 自动追加）。
CONTENT_STR = "正文内容"


def _auth(app, monkeypatch):
    """绕过会话登录，固定当前用户为 admin（id=1）。"""
    monkeypatch.setattr(web_app, "get_current_user", lambda sid: {"id": 1, "role": "admin"})


def _new_project(app):
    """创建一个协同创作项目，返回 project_id（id 嵌套在 project 下）。"""
    r = app.post("/api/collaborative/create", json={"title": "e2e"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["project"]["id"]


def test_e2e_full_flow(app, monkeypatch):
    """12.1 完整协同创作流程：idea → 选题 → 确认 → 大纲 → 内容 → 保存文章 → 含 AI 标识。"""
    _auth(app, monkeypatch)
    pid = _new_project(app)

    with patch("modules.ai_writer.generate_topics", return_value=TOPICS), \
         patch("modules.ai_writer.generate_outline", return_value=OUTLINE), \
         patch("modules.ai_writer.generate_content", return_value=CONTENT):
        # 生成选题
        r = app.post("/api/collaborative/topics", json={"idea": "AI 手机"})
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["topics"] == TOPICS

        # 确认选题（持久化到项目状态）
        r = app.post(f"/api/collaborative/{pid}/state",
                     json={"topic": TOPICS[0], "current_phase": "outline"})
        assert r.status_code == 200, r.get_json()

        # 生成大纲
        r = app.post("/api/collaborative/outline", json={"topic": TOPICS[0]["title"]})
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["outline"] == OUTLINE

        # 持久化大纲
        r = app.post(f"/api/collaborative/{pid}/state",
                     json={"outline": OUTLINE, "current_phase": "content"})
        assert r.status_code == 200, r.get_json()

        # 生成正文
        r = app.post("/api/collaborative/content", json={"outline": OUTLINE})
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["sections"] == CONTENT["sections"]

        # 持久化正文
        r = app.post(f"/api/collaborative/{pid}/state",
                     json={"content": CONTENT, "current_phase": "save"})
        assert r.status_code == 200, r.get_json()

        # 保存为历史文章（强制附加 AI 标识）
        r = app.post(f"/api/collaborative/{pid}/save-article", json={
            "title": "成品文章",
            "content": CONTENT_STR,
            "topic": TOPICS[0],
            "outline": OUTLINE,
        })
    assert r.status_code == 200, r.get_json()
    aid = r.get_json()["article_id"]
    assert aid

    # 验证持久化的文章包含 AI 标识
    art = ah.get_article(aid, 1)
    assert art is not None
    assert "AI" in art["ai_label"]
    assert DEFAULT_LABEL in art["content"]


def test_e2e_version_lifecycle(app, monkeypatch):
    """12.2 版本管理全流程：多次快照 → 列表 → 对比 → 回溯（产生新快照并恢复内容）。"""
    _auth(app, monkeypatch)
    pid = _new_project(app)

    v1 = create_snapshot(pid, 1, "v1", {"n": 1}, "manual")
    v2 = create_snapshot(pid, 1, "v2", {"n": 2}, "manual")

    # 列表：2 条，最新在前
    r = app.get(f"/api/collaborative/{pid}/versions")
    assert r.status_code == 200, r.get_json()
    versions = r.get_json()["versions"]
    assert len(versions) == 2
    assert versions[0]["version_name"] == "v2"
    assert versions[1]["version_name"] == "v1"

    # 对比 v1, v2：顶层标量 n 从 1 变为 2
    r = app.post(f"/api/collaborative/{pid}/versions/compare", json={"v1": v1, "v2": v2})
    assert r.status_code == 200, r.get_json()
    diff = r.get_json()["diff"]
    assert diff["changes"][0]["key"] == "n"
    assert diff["changes"][0]["old"] == 1
    assert diff["changes"][0]["new"] == 2

    # 回溯到 v1：产生第 3 条快照，内容为 v1 的内容
    r = app.post(f"/api/collaborative/{pid}/versions/{v1}/rollback")
    assert r.status_code == 200, r.get_json()
    new_id = r.get_json()["id"]
    assert new_id and new_id != v1

    r = app.get(f"/api/collaborative/{pid}/versions")
    assert r.status_code == 200
    versions = r.get_json()["versions"]
    assert len(versions) == 3
    # 最新快照的内容应恢复为 v1 的内容
    newest = versions[0]
    assert newest["id"] == new_id
    assert json.loads(newest["content_json"]) == {"n": 1}


def test_e2e_ai_label_blocked(app, monkeypatch):
    """12.3a 未带 AI 标识的内容保存应被拒绝（400）。"""
    _auth(app, monkeypatch)
    pid = _new_project(app)

    # 将 attach_label 替换为不追加标识的 no-op → 校验必败
    orig = ah.ai_labeler.attach_label
    ah.ai_labeler.attach_label = lambda c: c
    try:
        r = app.post(f"/api/collaborative/{pid}/save-article", json={
            "title": "无标识文章",
            "content": "没有标识的正文",
            "topic": {},
            "outline": {},
        })
    finally:
        ah.ai_labeler.attach_label = orig
    assert r.status_code == 400, r.get_json()


def test_e2e_admin_changes_label(app, monkeypatch):
    """12.3b 管理员修改标识文案后，新保存的文章使用新文案。"""
    _auth(app, monkeypatch)
    pid = _new_project(app)

    set_label_text("新标识文案", {"role": "admin"})
    r = app.post(f"/api/collaborative/{pid}/save-article", json={
        "title": "新标识文章",
        "content": "正文",
        "topic": {},
        "outline": {},
    })
    assert r.status_code == 200, r.get_json()
    aid = r.get_json()["article_id"]
    art = ah.get_article(aid, 1)
    assert art["ai_label"] == "新标识文案"
    assert "新标识文案" in art["content"]
    # 恢复默认，避免污染其他测试
    set_label_text(DEFAULT_LABEL, {"role": "admin"})


def test_e2e_history_management(app, monkeypatch):
    """12.4 历史文章管理：保存多篇 → 列表 → 详情 → 继续编辑 → 删除。"""
    _auth(app, monkeypatch)
    pid = _new_project(app)

    # 保存两篇文章
    r1 = app.post(f"/api/collaborative/{pid}/save-article", json={
        "title": "文章一", "content": "正文一", "topic": {}, "outline": {},
    })
    assert r1.status_code == 200, r1.get_json()
    aid1 = r1.get_json()["article_id"]

    r2 = app.post(f"/api/collaborative/{pid}/save-article", json={
        "title": "文章二", "content": "正文二", "topic": {}, "outline": {},
    })
    assert r2.status_code == 200, r2.get_json()
    aid2 = r2.get_json()["article_id"]

    # 列表：2 条，最新在前
    r = app.get("/api/collaborative/articles")
    assert r.status_code == 200, r.get_json()
    articles = r.get_json()["articles"]
    assert len(articles) == 2
    assert articles[0]["title"] == "文章二"

    # 详情
    r = app.get(f"/api/collaborative/articles/{aid1}")
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["article"]["title"] == "文章一"

    # 继续编辑：基于文章一新建项目，预填充其内容
    r = app.post(f"/api/collaborative/articles/{aid1}/continue")
    assert r.status_code == 200, r.get_json()
    new_pid = r.get_json()["project_id"]
    r = app.get(f"/api/collaborative/{new_pid}")
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["project"]["title"] == "文章一"

    # 删除
    r = app.delete(f"/api/collaborative/articles/{aid1}")
    assert r.status_code == 200, r.get_json()
    r = app.get(f"/api/collaborative/articles/{aid1}")
    assert r.status_code == 404


def test_e2e_platform_removed(app, monkeypatch):
    """12.5 平台功能完全移除：模块/路由/配置均不可访问。"""
    _auth(app, monkeypatch)

    # 四个平台模块已删除
    for name in ["wx_publisher.py", "md_converter.py", "cover_generator.py", "cover_maker.py"]:
        assert not os.path.exists(os.path.join(ROOT, "modules", name)), f"{name} 应被删除"

    # domains_config.json 是通用选题配置（与特定平台无关），应保留
    assert os.path.exists(os.path.join(ROOT, "domains_config.json"))

    # 平台前端路由已移除
    assert app.get("/cover_maker.html").status_code == 404
