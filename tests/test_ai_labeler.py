"""
tests/test_ai_labeler.py
AI 标识模块的回归测试
"""
import pytest
from modules import ai_labeler

DEFAULT = "本文由 AI 辅助生成，请仔细甄别文章内容。"


def test_get_label_text_default(db):
    assert ai_labeler.get_label_text() == DEFAULT


def test_attach_label_appends(db):
    out = ai_labeler.attach_label("正文内容")
    assert "正文内容" in out
    assert DEFAULT in out


def test_validate_content_ok(db):
    assert ai_labeler.validate_content("正文\n\n" + DEFAULT) is True


def test_validate_content_fail(db):
    assert ai_labeler.validate_content("没有标识的正文") is False


def test_set_label_text_admin(db):
    ok = ai_labeler.set_label_text("新标识文案", {"id": 1, "role": "admin"})
    assert ok is True
    assert ai_labeler.get_label_text() == "新标识文案"


def test_set_label_text_non_admin_forbidden(db):
    # restore default first so the forbidden-test assertion is stable
    ai_labeler.set_label_text(DEFAULT, {"id": 1, "role": "admin"})
    with pytest.raises(PermissionError):
        ai_labeler.set_label_text("hack", {"id": 2, "role": "user"})
    assert ai_labeler.get_label_text() == DEFAULT
