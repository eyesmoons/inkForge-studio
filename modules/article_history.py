"""
article_history.py
历史文章管理：保存/列表/获取/更新/删除。

集成 ai_labeler：保存或更新内容时自动追加 AI 标识并校验。
"""
import json

from modules.user_db import get_db
from modules import ai_labeler


def save_article(user_id, title, topic_json, outline_json, content) -> int:
    """保存一篇已完成文章。

    先通过 ai_labeler.attach_label 追加 AI 标识，再校验；校验失败抛出 ValueError。
    返回新文章 id。
    """
    labeled = ai_labeler.attach_label(content)
    if not ai_labeler.validate_content(labeled):
        raise ValueError("内容缺少 AI 标识，无法保存")
    label = ai_labeler.get_label_text()
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            """
            INSERT INTO article_history
                (user_id, title, topic_json, outline_json, content_json, ai_label,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                title,
                json.dumps(topic_json, ensure_ascii=False),
                json.dumps(outline_json, ensure_ascii=False),
                labeled,
                label,
            ),
        )
        db.conn.commit()
        return cur.lastrowid


def list_articles(user_id) -> list:
    """列出用户文章，按 created_at DESC, id DESC（最新优先）。"""
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, title, topic_json, outline_json,
                   content_json AS content, ai_label, created_at, updated_at
            FROM article_history
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_articles_paginated(user_id: int, page: int = 1, page_size: int = 10, keyword: str = None) -> dict:
    """分页列出用户文章（协同创作产出的 article_history）。

    返回 {"articles": [...], "pagination": {...}}，与 /api/articles 契约一致。
    """
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()

        # 过滤条件
        where = "WHERE user_id = ?"
        params = [user_id]
        if keyword:
            where += " AND (title LIKE ? OR content_json LIKE ?)"
            kw = f"%{keyword}%"
            params.extend([kw, kw])

        # 总数
        cur.execute(f"SELECT COUNT(*) AS total FROM article_history {where}", params)
        total = cur.fetchone()["total"]
        total_pages = max(1, (total + page_size - 1) // page_size) if total else 0

        # 分页数据
        offset = (page - 1) * page_size
        cur.execute(
            f"""
            SELECT id, user_id, title, topic_json, outline_json,
                   content_json AS content, ai_label, created_at, updated_at
            FROM article_history
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        )
        articles = [dict(row) for row in cur.fetchall()]

        return {
            "articles": articles,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        }


def get_article(article_id, user_id):
    """获取属于 user_id 的某篇文章；不存在或不属于该用户返回 None。"""
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, title, topic_json, outline_json,
                   content_json AS content, ai_label, created_at, updated_at
            FROM article_history
            WHERE id = ? AND user_id = ?
            """,
            (article_id, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_article(article_id, user_id, **fields) -> bool:
    """更新允许字段（title, topic_json, outline_json, content）。

    若更新 content，则重新附加 AI 标识并校验（失败抛出 ValueError）。
    返回是否有行被更新。
    """
    ALLOWED = {"title", "topic_json", "outline_json", "content"}

    updates = {k: v for k, v in fields.items() if k in ALLOWED}
    if not updates:
        return False

    set_clauses = []
    params = []

    for key, value in updates.items():
        if key == "content":
            value = ai_labeler.attach_label(value)
            if not ai_labeler.validate_content(value):
                raise ValueError("内容缺少 AI 标识，无法保存")
            set_clauses.append("content_json = ?")
        elif key in ("topic_json", "outline_json"):
            value = json.dumps(value, ensure_ascii=False)
            set_clauses.append(f"{key} = ?")
        else:
            set_clauses.append(f"{key} = ?")
        params.append(value)

    if "content" in updates:
        set_clauses.append("ai_label = ?")
        params.append(ai_labeler.get_label_text())

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([article_id, user_id])

    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            f"UPDATE article_history SET {', '.join(set_clauses)} "
            "WHERE id = ? AND user_id = ?",
            params,
        )
        db.conn.commit()
        return cur.rowcount > 0


def delete_article(article_id, user_id) -> bool:
    """删除属于 user_id 的某篇文章。返回是否有行被删除。"""
    with get_db() as db:
        db._connect()
        cur = db.conn.cursor()
        cur.execute(
            "DELETE FROM article_history WHERE id = ? AND user_id = ?",
            (article_id, user_id),
        )
        db.conn.commit()
        return cur.rowcount > 0
