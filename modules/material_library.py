"""
modules/material_library.py
素材库管理模块 — 收藏、查看、删除、标签管理、分组管理、上传

素材来源：
  - 从封面制作收藏
  - 从本地上传
  - 从其他模块收藏（后续扩展）
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).parent.parent
MATERIAL_DIR = BASE_DIR / "output" / "materials"
MATERIAL_DIR.mkdir(parents=True, exist_ok=True)

# 允许的图片扩展名
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


# ════════════════════════════════════════════════════════════
# 分组管理
# ════════════════════════════════════════════════════════════

def get_groups(user_id: int) -> List[Dict]:
    """获取用户的素材分组列表"""
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            cur.execute(
                """
                SELECT g.id, g.name, g.sort_order, g.created_at,
                       (SELECT COUNT(*) FROM material_library WHERE group_id = g.id) AS item_count
                FROM material_groups g
                WHERE g.user_id = ?
                ORDER BY g.sort_order, g.id
                """,
                (user_id,)
            )
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[material_library] 获取分组失败: {e}")
        return []


def create_group(user_id: int, name: str, sort_order: int = 0) -> Dict:
    """创建素材分组"""
    name = name.strip()[:50]
    if not name:
        return {"ok": False, "error": "分组名称不能为空"}

    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            # 检查同名
            cur.execute(
                "SELECT id FROM material_groups WHERE user_id = ? AND name = ?",
                (user_id, name)
            )
            if cur.fetchone():
                return {"ok": False, "error": f"分组「{name}」已存在"}

            cur.execute(
                "INSERT INTO material_groups (user_id, name, sort_order) VALUES (?, ?, ?)",
                (user_id, name, sort_order)
            )
            db.conn.commit()
            return {"ok": True, "id": cur.lastrowid}
    except Exception as e:
        return {"ok": False, "error": f"创建分组失败: {str(e)}"}


def update_group(group_id: int, user_id: int, name: str = None, sort_order: int = None) -> Dict:
    """更新素材分组"""
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            fields = []
            values = []

            if name is not None:
                name = name.strip()[:50]
                if not name:
                    return {"ok": False, "error": "分组名称不能为空"}
                # 检查同名
                cur.execute(
                    "SELECT id FROM material_groups WHERE user_id = ? AND name = ? AND id != ?",
                    (user_id, name, group_id)
                )
                if cur.fetchone():
                    return {"ok": False, "error": f"分组「{name}」已存在"}
                fields.append("name = ?")
                values.append(name)

            if sort_order is not None:
                fields.append("sort_order = ?")
                values.append(sort_order)

            if not fields:
                return {"ok": False, "error": "没有需要更新的字段"}

            values.extend([group_id, user_id])
            cur.execute(
                f"UPDATE material_groups SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                values
            )
            db.conn.commit()
            return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"更新分组失败: {str(e)}"}


def delete_group(group_id: int, user_id: int, move_to_none: bool = True) -> Dict:
    """
    删除素材分组

    Args:
        move_to_none: True=将分组内素材移到未分组, False=连同素材一起删除
    """
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            # 检查分组存在
            cur.execute(
                "SELECT id FROM material_groups WHERE id = ? AND user_id = ?",
                (group_id, user_id)
            )
            if not cur.fetchone():
                return {"ok": False, "error": "分组不存在"}

            if move_to_none:
                # 将分组内素材移到未分组
                cur.execute(
                    "UPDATE material_library SET group_id = NULL WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id)
                )
            else:
                # 删除分组内所有素材（包括文件）
                cur.execute(
                    "SELECT filename FROM material_library WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id)
                )
                for row in cur.fetchall():
                    filename = row["filename"]
                    if filename.startswith("mat_"):
                        file_path = MATERIAL_DIR / filename
                    elif filename.startswith("upload_"):
                        file_path = MATERIAL_DIR / filename
                    else:
                        file_path = BASE_DIR / "output" / "covers" / filename
                    if file_path.exists():
                        file_path.unlink()

                cur.execute(
                    "DELETE FROM material_library WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id)
                )

            # 删除分组
            cur.execute(
                "DELETE FROM material_groups WHERE id = ? AND user_id = ?",
                (group_id, user_id)
            )
            db.conn.commit()
            return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"删除分组失败: {str(e)}"}


def move_material_to_group(material_id: int, user_id: int, group_id: int = None) -> Dict:
    """将素材移到指定分组（group_id=None 表示未分组）"""
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            # 如果指定了分组，验证分组归属
            if group_id is not None:
                cur.execute(
                    "SELECT id FROM material_groups WHERE id = ? AND user_id = ?",
                    (group_id, user_id)
                )
                if not cur.fetchone():
                    return {"ok": False, "error": "分组不存在"}

            cur.execute(
                "UPDATE material_library SET group_id = ? WHERE id = ? AND user_id = ?",
                (group_id, material_id, user_id)
            )
            db.conn.commit()
            return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"移动失败: {str(e)}"}


# ════════════════════════════════════════════════════════════
# 收藏到素材库（去重）
# ════════════════════════════════════════════════════════════

def add_to_library(
    user_id: int,
    title: str = "",
    tags: str = "",
    source_type: str = "cover",
    source_id: int = None,
    filename: str = "",
    image_url: str = "",
    prompt: str = "",
    notes: str = "",
    group_id: int = None,
) -> Dict:
    """
    收藏图片到素材库（支持去重检查）

    Args:
        user_id: 用户ID
        title: 素材标题
        tags: 标签（逗号分隔）
        source_type: 来源类型（cover/upload/other）
        source_id: 来源ID（如封面记录ID）
        filename: 源文件名
        image_url: 源图片URL路径
        prompt: 生成prompt
        notes: 备注
        group_id: 分组ID

    Returns:
        {"ok": True, "id": ...} 或 {"ok": False, "error": "..."}
    """
    if not filename:
        return {"ok": False, "error": "文件名不能为空"}

    # 去重检查：同一用户同一源文件不能重复收藏
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            cur.execute(
                "SELECT id FROM material_library WHERE user_id = ? AND filename = ?",
                (user_id, f"mat_{filename}" if source_type == "cover" else filename)
            )
            if cur.fetchone():
                return {"ok": False, "error": "该图片已在素材库中，不要重复收藏"}
    except Exception:
        pass

    # 复制图片到素材库目录
    source_path = None
    # 根据来源类型查找源文件
    if source_type == "cover":
        source_path = BASE_DIR / "output" / "covers" / filename

    if source_path and source_path.exists():
        # 复制到素材库目录（保留原文件，避免删除封面后素材库丢失）
        material_filename = f"mat_{filename}"
        target_path = MATERIAL_DIR / material_filename
        shutil.copy2(str(source_path), str(target_path))
        material_image_url = f"/api/material_library/image/{material_filename}"
    else:
        # 源文件不存在，只保存记录
        material_filename = filename
        material_image_url = image_url

    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT INTO material_library (
                    user_id, group_id, title, tags, source_type, source_id,
                    filename, image_url, prompt, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    group_id,
                    title[:100],
                    tags[:200],
                    source_type,
                    source_id,
                    material_filename,
                    material_image_url,
                    prompt[:1000],
                    notes[:500],
                )
            )
            db.conn.commit()
            new_id = cur.lastrowid

            # 更新 cover_generations 的 is_collected 标记
            if source_type == "cover" and source_id:
                try:
                    db.conn.execute(
                        "UPDATE cover_generations SET is_collected = 1 WHERE id = ? AND user_id = ?",
                        (source_id, user_id)
                    )
                    db.conn.commit()
                except Exception:
                    pass

            return {"ok": True, "id": new_id}
    except Exception as e:
        return {"ok": False, "error": f"收藏失败: {str(e)}"}


# ════════════════════════════════════════════════════════════
# 上传本地图片
# ════════════════════════════════════════════════════════════

def upload_image(
    user_id: int,
    file_data: bytes,
    original_filename: str,
    title: str = "",
    tags: str = "",
    group_id: int = None,
    notes: str = "",
) -> Dict:
    """
    上传本地图片到素材库

    Args:
        user_id: 用户ID
        file_data: 文件二进制数据
        original_filename: 原始文件名
        title: 素材标题
        tags: 标签
        group_id: 分组ID
        notes: 备注

    Returns:
        {"ok": True, "id": ...} 或 {"ok": False, "error": "..."}
    """
    # 检查文件扩展名
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"ok": False, "error": f"不支持的文件格式: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}"}

    # 检查文件大小（最大 10MB）
    if len(file_data) > 10 * 1024 * 1024:
        return {"ok": False, "error": "文件大小不能超过 10MB"}

    # 生成唯一文件名
    filename = f"upload_{uuid.uuid4().hex[:12]}{ext}"
    target_path = MATERIAL_DIR / filename

    # 保存文件
    with open(target_path, "wb") as f:
        f.write(file_data)

    image_url = f"/api/material_library/image/{filename}"

    if not title:
        title = Path(original_filename).stem

    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT INTO material_library (
                    user_id, group_id, title, tags, source_type,
                    filename, image_url, prompt, notes
                ) VALUES (?, ?, ?, ?, 'upload', ?, ?, '', ?)
                """,
                (
                    user_id,
                    group_id,
                    title[:100],
                    tags[:200],
                    filename,
                    image_url,
                    notes[:500],
                )
            )
            db.conn.commit()
            new_id = cur.lastrowid
            return {"ok": True, "id": new_id, "filename": filename}
    except Exception as e:
        # 清理已保存的文件
        if target_path.exists():
            target_path.unlink()
        return {"ok": False, "error": f"上传失败: {str(e)}"}


# ════════════════════════════════════════════════════════════
# 查询
# ════════════════════════════════════════════════════════════

def get_materials(
    user_id: int,
    group_id: int = None,
    tag: str = None,
    source_type: str = None,
    keyword: str = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict:
    """
    获取素材库列表（支持筛选和搜索）

    Args:
        user_id: 用户ID
        group_id: 按分组筛选（0=未分组, None=不限）
        tag: 按标签筛选
        source_type: 按来源类型筛选
        keyword: 关键词搜索（标题/备注）
        limit: 每页数量
        offset: 偏移量

    Returns:
        {"ok": True, "data": [...], "total": N}
    """
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()

            # 构建查询条件
            conditions = ["m.user_id = ?"]
            params = [user_id]

            if group_id is not None:
                if group_id == 0:
                    conditions.append("m.group_id IS NULL")
                else:
                    conditions.append("m.group_id = ?")
                    params.append(group_id)

            if tag:
                conditions.append("m.tags LIKE ?")
                params.append(f"%{tag}%")

            if source_type:
                conditions.append("m.source_type = ?")
                params.append(source_type)

            if keyword:
                conditions.append("(m.title LIKE ? OR m.notes LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            where_clause = " AND ".join(conditions)

            # 统计总数
            cur.execute(
                f"SELECT COUNT(*) as total FROM material_library m WHERE {where_clause}",
                params
            )
            total = cur.fetchone()["total"]

            # 分页查询（带分组名称）
            cur.execute(
                f"""
                SELECT m.id, m.group_id, m.title, m.tags, m.source_type, m.source_id,
                       m.filename, m.image_url, m.prompt, m.notes, m.created_at,
                       g.name AS group_name
                FROM material_library m
                LEFT JOIN material_groups g ON m.group_id = g.id
                WHERE {where_clause}
                ORDER BY m.created_at DESC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset]
            )
            rows = cur.fetchall()

            items = []
            for row in rows:
                item = dict(row)
                # 检查图片文件是否存在
                filename = item.get("filename", "")
                if filename.startswith("mat_") or filename.startswith("upload_"):
                    image_path = MATERIAL_DIR / filename
                else:
                    image_path = BASE_DIR / "output" / "covers" / filename

                if not image_path.exists():
                    item["image_missing"] = True

                items.append(item)

            return {"ok": True, "data": items, "total": total}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_material_by_id(material_id: int, user_id: int) -> Optional[Dict]:
    """获取单个素材详情"""
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            cur.execute(
                """
                SELECT m.id, m.group_id, m.title, m.tags, m.source_type, m.source_id,
                       m.filename, m.image_url, m.prompt, m.notes, m.created_at,
                       g.name AS group_name
                FROM material_library m
                LEFT JOIN material_groups g ON m.group_id = g.id
                WHERE m.id = ? AND m.user_id = ?
                """,
                (material_id, user_id)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def update_material(
    material_id: int,
    user_id: int,
    title: str = None,
    tags: str = None,
    notes: str = None,
    group_id: int = None,
) -> bool:
    """更新素材信息（标题、标签、备注、分组）"""
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()

            fields = []
            values = []

            if title is not None:
                fields.append("title = ?")
                values.append(title[:100])
            if tags is not None:
                fields.append("tags = ?")
                values.append(tags[:200])
            if notes is not None:
                fields.append("notes = ?")
                values.append(notes[:500])
            if group_id is not None:
                fields.append("group_id = ?")
                values.append(group_id)

            if not fields:
                return False

            values.extend([material_id, user_id])
            cur.execute(
                f"UPDATE material_library SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                values
            )
            db.conn.commit()
            return cur.rowcount > 0
    except Exception:
        return False


def delete_material(material_id: int, user_id: int) -> bool:
    """删除素材（记录+文件）"""
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            # 先获取文件名和来源信息
            cur.execute(
                "SELECT filename, source_type, source_id FROM material_library WHERE id = ? AND user_id = ?",
                (material_id, user_id)
            )
            row = cur.fetchone()
            if not row:
                return False

            filename = row["filename"]
            source_type = row["source_type"]
            source_id = row["source_id"]

            # 删除数据库记录
            cur.execute(
                "DELETE FROM material_library WHERE id = ? AND user_id = ?",
                (material_id, user_id)
            )
            db.conn.commit()

            # 如果是封面收藏，更新 is_collected 标记
            if source_type == "cover" and source_id:
                try:
                    db.conn.execute(
                        "UPDATE cover_generations SET is_collected = 0 WHERE id = ? AND user_id = ?",
                        (source_id, user_id)
                    )
                    db.conn.commit()
                except Exception:
                    pass

            # 删除素材文件
            if filename.startswith("mat_") or filename.startswith("upload_"):
                file_path = MATERIAL_DIR / filename
            else:
                file_path = BASE_DIR / "output" / "covers" / filename

            if file_path.exists():
                file_path.unlink()

            return True
    except Exception as e:
        print(f"[material_library] 删除素材失败：{e}")
        return False


def get_all_tags(user_id: int) -> List[str]:
    """获取用户素材库中所有标签（去重）"""
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            cur = db.conn.cursor()
            cur.execute(
                "SELECT DISTINCT tags FROM material_library WHERE user_id = ? AND tags != ''",
                (user_id,)
            )
            rows = cur.fetchall()

            # 展开逗号分隔的标签
            tag_set = set()
            for row in rows:
                for tag in row["tags"].split(","):
                    tag = tag.strip()
                    if tag:
                        tag_set.add(tag)

            return sorted(tag_set)
    except Exception:
        return []
