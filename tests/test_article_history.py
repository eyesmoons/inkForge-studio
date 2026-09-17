"""article_history 模块测试：保存/列表/获取/更新/删除，以及 AI 标识集成。"""
import pytest
from modules import article_history
from modules.ai_labeler import DEFAULT_LABEL, attach_label, validate_content


def _payload(title="t"):
    return {
        "user_id": 1,
        "title": title,
        "topic_json": {"title": "选题"},
        "outline_json": {"sections": []},
        "content": "正文内容",
    }


def test_save_article_appends_label(db):
    aid = article_history.save_article(**_payload())
    art = article_history.get_article(aid, user_id=1)
    assert art is not None
    assert DEFAULT_LABEL in art["content"]
    assert art["ai_label"] == DEFAULT_LABEL


def test_save_article_validates_and_blocks_plain_content(db):
    # attach_label 在 save 内部总会被调用，所以要走到校验失败路径，
    # 需将 attach_label 替换为不追加标识的版本。
    from modules import article_history as ah
    orig = ah.ai_labeler.attach_label
    ah.ai_labeler.attach_label = lambda c: c  # 去掉标识 -> 校验必败
    try:
        with pytest.raises(ValueError):
            article_history.save_article(**_payload(title="no-label"))
    finally:
        ah.ai_labeler.attach_label = orig


def test_list_articles_order(db):
    article_history.save_article(**_payload(title="first"))
    article_history.save_article(**_payload(title="second"))
    items = article_history.list_articles(user_id=1)
    assert [a["title"] for a in items] == ["second", "first"]


def test_get_article_ownership(db):
    aid = article_history.save_article(**_payload())
    assert article_history.get_article(aid, user_id=1) is not None
    assert article_history.get_article(aid, user_id=999) is None


def test_update_article_relabels(db):
    aid = article_history.save_article(**_payload())
    ok = article_history.update_article(aid, user_id=1, content="新正文")
    assert ok is True
    art = article_history.get_article(aid, user_id=1)
    assert DEFAULT_LABEL in art["content"]


def test_delete_article(db):
    aid = article_history.save_article(**_payload())
    assert article_history.delete_article(aid, user_id=1) is True
    assert article_history.get_article(aid, user_id=1) is None
    assert article_history.delete_article(aid, user_id=1) is False
