"""
modules/image_generator.py
AI 配图模块 — 根据文字描述生成文章插图（人机协同写作）。

调用用户在「AI 模型管理」中配置的图像生成模型（is_image_model = 1），
走 OpenAI 兼容的 /images/generations 接口；生成后下载到本地素材目录，
并自动收藏到素材库。
"""

import os
import uuid
import shutil
import hashlib
import requests
from pathlib import Path
from typing import Dict, Optional

BASE_DIR = Path(__file__).parent.parent
MATERIAL_DIR = BASE_DIR / "output" / "materials"
MATERIAL_DIR.mkdir(parents=True, exist_ok=True)

# 图片生成接口路径（OpenAI 兼容）
IMAGE_GENERATION_SUFFIX = "/images/generations"

# 默认出图尺寸
DEFAULT_SIZE = "1024x1024"


def _get_image_model(user_id: int) -> Optional[Dict]:
    """读取用户默认的图像生成模型配置（含 api_key / api_base / model_name）。"""
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            return db.get_user_default_image_model(user_id)
    except Exception:
        return None


def _download_image(url: str, dest_path: Path) -> bool:
    """下载图片到本地路径。"""
    try:
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(resp.raw, f)
        return dest_path.exists() and dest_path.stat().st_size > 0
    except Exception:
        return False


def generate_image(
    prompt: str,
    user_id: int,
    size: str = DEFAULT_SIZE,
    save_to_library: bool = True,
) -> Dict:
    """
    根据 prompt 生成插图。

    Args:
        prompt:        图片描述文本
        user_id:       用户 ID（用于读取图像模型配置 + 收藏）
        size:          出图尺寸（默认 1024x1024）
        save_to_library: 是否自动收藏到素材库

    Returns:
        {"ok": True, "url": "/api/material_library/image/xxx.jpg", "id": 素材ID}
        或 {"ok": False, "error": "..."}
    """
    if not prompt or not prompt.strip():
        return {"ok": False, "error": "请描述你想要的插图内容"}

    model = _get_image_model(user_id)
    if not model:
        return {
            "ok": False,
            "error": "尚未配置图像生成模型。请先到「系统配置 → AI 模型管理」添加并启用一个图像生成模型。",
        }

    api_key = model.get("api_key", "")
    api_base = model.get("api_base", "").rstrip("/")
    model_name = model.get("model_name", "")
    if not api_key or not api_base or not model_name:
        return {"ok": False, "error": "图像生成模型配置不完整（缺少 api_key / api_base / model_name）。"}

    api_url = f"{api_base}{IMAGE_GENERATION_SUFFIX}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "prompt": prompt.strip(),
        "size": size,
        "n": 1,
    }

    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=120)
    except Exception as e:
        return {"ok": False, "error": f"请求图像生成接口失败：{e}"}

    if resp.status_code != 200:
        err_text = resp.text[:300]
        return {"ok": False, "error": f"图像生成失败（HTTP {resp.status_code}）：{err_text}"}

    try:
        data = resp.json()
    except Exception:
        return {"ok": False, "error": "图像生成接口返回了无法解析的内容。"}

    # 取第一张图的 url 或 b64
    item = (data.get("data") or [{}])[0]
    image_url = item.get("url")
    b64 = item.get("b64_json")

    if not image_url and not b64:
        return {"ok": False, "error": "图像生成接口未返回图片数据。"}

    # 落到本地素材目录
    ext = ".png" if b64 else (".jpg" if ".jpg" in image_url or ".jpeg" in image_url else ".png")
    local_name = f"img_{uuid.uuid4().hex[:12]}{ext}"
    local_path = MATERIAL_DIR / local_name

    ok = False
    if image_url:
        ok = _download_image(image_url, local_path)
    else:
        try:
            import base64
            with open(local_path, "wb") as f:
                f.write(base64.b64decode(b64))
            ok = local_path.exists()
        except Exception:
            ok = False

    if not ok:
        return {"ok": False, "error": "图片生成成功但下载到本地失败，请重试。"}

    public_url = f"/api/material_library/image/{local_name}"

    # 自动收藏到素材库
    material_id = None
    if save_to_library:
        try:
            from modules.material_library import add_to_library
            r = add_to_library(
                user_id=user_id,
                title=prompt.strip()[:30],
                tags="ai配图,AI生成",
                source_type="ai_image",
                filename=local_name,
                image_url=public_url,
                prompt=prompt.strip(),
            )
            if r.get("ok"):
                material_id = r.get("id")
        except Exception:
            pass

    return {"ok": True, "url": public_url, "id": material_id, "filename": local_name}
