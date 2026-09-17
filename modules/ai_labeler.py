"""
ai_labeler.py
AI 标识模块：读取/附加/校验/修改文章末尾 AI 标识文案。

依赖 modules.user_db.get_db 访问 ai_label_config 表（单行 id=1）。
"""
from modules.user_db import get_db

DEFAULT_LABEL = "本文由 AI 辅助生成，请仔细甄别文章内容。"


def get_label_text() -> str:
    """读取当前 AI 标识文案，缺失或为空时返回默认值。"""
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute("SELECT label_text FROM ai_label_config WHERE id = 1")
        row = cur.fetchone()
    if not row:
        return DEFAULT_LABEL
    value = row["label_text"]
    if not value:
        return DEFAULT_LABEL
    return value


def attach_label(content) -> str:
    """将标识文案追加到内容末尾（幂等：已包含则原样返回）。"""
    label = get_label_text()
    text = content or ""
    if label in text:
        return text
    return f"{text.rstrip()}\n\n{label}"


def validate_content(content) -> bool:
    """判断内容中是否包含当前标识文案。"""
    return get_label_text() in (content or "")


def set_label_text(new_text, admin_user) -> bool:
    """仅管理员可修改标识文案，更新 ai_label_config 表 id=1 行。"""
    if not admin_user or admin_user.get("role") != "admin":
        raise PermissionError("仅管理员可修改 AI 标识文案")
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            "UPDATE ai_label_config SET label_text = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ? WHERE id = 1",
            (new_text, admin_user.get("id")),
        )
        db.conn.commit()
        return cur.rowcount > 0
