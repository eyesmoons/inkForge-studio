"""
modules/cover_maker.py
AI 封面制作模块 — 根据标题/内容生成微信公众号封面图

支持的后端（OpenAI-compatible /v1/images/generations 接口）：
  - OpenAI DALL-E 3
  - 智谱 CogView (https://open.bigmodel.cn/api/paas/v4)
  - 硅基流动 SiliconFlow (https://api.siliconflow.cn/v1)
  - 通义万相 (https://dashscope.aliyuncs.com/compatible-mode/v1)
  - 任何兼容 /v1/images/generations 的服务

配置优先级：
  1. 数据库中的封面生成专用配置（cover_api_key / cover_api_base / cover_model）
  2. 项目的 AI 模型配置（复用 ai_assistant 的配置体系）
  3. 环境变量 COVER_API_KEY / COVER_API_BASE / COVER_MODEL
"""

import os
import json
import time
import base64
import requests
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output" / "covers"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════════
# 配置获取
# ════════════════════════════════════════════════════════════

# 国内可用的图像生成服务默认配置
IMAGE_PROVIDERS = {
    "siliconflow": {
        "name": "硅基流动",
        "api_base": "https://api.siliconflow.cn/v1",
        "model": "black-forest-labs/FLUX.1-schnell",
        "doc": "https://cloud.siliconflow.cn 注册获取 API Key",
    },
    "zhipu": {
        "name": "智谱 CogView",
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "model": "cogview-4",
        "doc": "https://open.bigmodel.cn 注册获取 API Key",
    },
    "dashscope": {
        "name": "通义万相",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "wanx2.1-t2i-turbo",
        "doc": "https://dashscope.console.aliyun.com 开通获取 API Key",
    },
    "doubao": {
        "name": "豆包（火山引擎）",
        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seedream-3-0-t2i-250415",
        "doc": "https://console.volcengine.com/ark 开通获取 API Key",
    },
    "dalle": {
        "name": "OpenAI DALL-E 3",
        "api_base": "https://api.openai.com/v1",
        "model": "dall-e-3",
        "doc": "https://platform.openai.com 需海外网络",
    },
}


def _get_cover_config(user_id: int = None) -> Dict:
    """获取封面生成专用配置"""
    # 1. 优先从数据库获取标记为图像模型(is_image_model=1)的配置
    try:
        from modules.user_db import UserDB
        with UserDB() as db:
            image_model = db.get_user_default_image_model(user_id)
            if image_model and image_model.get("api_key"):
                api_base = image_model.get("api_base", "")
                model_name = image_model.get("model_name", "")
                return {
                    "api_key": image_model["api_key"],
                    "api_base": api_base,
                    "model": model_name,
                }
    except Exception:
        pass

    # 2. 环境变量（兜底）
    env_key = os.environ.get("COVER_API_KEY", "").strip()
    if env_key:
        return {
            "api_key": env_key,
            "api_base": os.environ.get("COVER_API_BASE", "https://api.siliconflow.cn/v1").strip(),
            "model": os.environ.get("COVER_MODEL", "black-forest-labs/FLUX.1-schnell").strip(),
        }

    # 未配置
    return {"api_key": "", "api_base": "", "model": ""}


# ════════════════════════════════════════════════════════════
# Prompt 工程 — 去除 AI 味
# ════════════════════════════════════════════════════════════

STYLE_PRESETS = {
    "minimal": {
        "name": "极简商务",
        "prompt": "Clean minimalist business cover, solid or subtle gradient background, lots of white space, bold modern Chinese typography as the visual focus, no decorative elements, professional and elegant, editorial magazine style",
    },
    "tech": {
        "name": "科技感",
        "prompt": "Futuristic tech cover, dark navy or deep blue background with subtle glowing circuit lines or data particles, holographic accent, sleek modern feel, no text in image",
    },
    "warm": {
        "name": "温暖人文",
        "prompt": "Warm lifestyle cover, soft natural lighting, cozy scene with coffee cup and notebook on wooden desk or sunlit window, warm earth tones, inviting and genuine, editorial photography style, no text in image",
    },
    "nature": {
        "name": "自然风景",
        "prompt": "Stunning nature photography cover, dramatic landscape with golden hour light, mountains or ocean or forest, vivid colors, National Geographic style, photorealistic, no text in image",
    },
    "abstract": {
        "name": "抽象艺术",
        "prompt": "Abstract art cover, flowing organic shapes with subtle color transitions, muted elegant palette, contemporary art gallery feel, no text in image, no geometric patterns",
    },
    "news": {
        "name": "新闻资讯",
        "prompt": "Professional news cover, clean layout with subtle newspaper texture overlay, bold red or blue accent stripe, journalistic feel, serious and authoritative, no text in image",
    },
    "food": {
        "name": "美食生活",
        "prompt": "Appetizing food photography cover, beautifully plated dish with natural lighting, shallow depth of field, warm color palette, editorial food magazine style, photorealistic, no text in image",
    },
    "city": {
        "name": "城市建筑",
        "prompt": "Architectural photography cover, modern city skyline or building detail at blue hour, clean geometric lines, dramatic perspective, professional photography, no text in image",
    },
}

COVER_SIZES = {
    "wide": {"name": "横版封面 (2.35:1)", "width": 900, "height": 383},
    "square": {"name": "正方形 (1:1)", "width": 600, "height": 600},
}


def _build_image_prompt(title: str, content: str = "", style: str = "minimal",
                        custom_prompt: str = "") -> str:
    """构建图像生成 Prompt，核心策略：叠加风格预设 + 去AI味约束"""
    style_info = STYLE_PRESETS.get(style, STYLE_PRESETS["minimal"])

    subject = ""
    if title:
        subject = title.strip()[:100]
    if content:
        subject += f" — {content.strip()[:200]}"

    if custom_prompt:
        base_prompt = custom_prompt
    else:
        base_prompt = f"WeChat article cover image, subject: {subject}. {style_info['prompt']}"

    anti_ai = (
        "CRITICAL RULES: "
        "Do NOT include any text, letters, Chinese characters, or watermarks in the image. "
        "Do NOT generate overly smooth, plastic-like, or hyper-saturated AI-art style. "
        "Aim for photorealistic or high-quality editorial illustration style. "
        "Natural lighting, natural textures, subtle imperfections are preferred. "
        "Avoid shiny/glossy effects. Avoid rainbow gradients. Avoid 3D rendered look. "
        "The image should look like it was taken by a professional photographer or designed by a human graphic designer."
    )

    return f"{base_prompt}. {anti_ai}"


# ════════════════════════════════════════════════════════════
# 图像生成 API 调用
# ════════════════════════════════════════════════════════════

def _determine_size_param(size: str, model: str) -> str:
    """根据模型确定可用的尺寸参数"""
    model_lower = model.lower()

    # DALL-E 3 只支持 1024x1024, 1792x1024, 1024x1792
    if "dall-e" in model_lower or "dalle" in model_lower:
        return "1792x1024" if size == "wide" else "1024x1024"

    # FLUX 模型支持常见尺寸
    if "flux" in model_lower:
        return "1024x576" if size == "wide" else "1024x1024"

    # CogView-4 / glm-image
    if "cogview" in model_lower or "glm-image" in model_lower:
        if "glm-image" in model_lower:
            return "1728x960" if size == "wide" else "1280x1280"
        return "1024x576" if size == "wide" else "1024x1024"

    # 通义万相
    if "wanx" in model_lower:
        return "1024*576" if size == "wide" else "1024*1024"

    # 豆包
    if "doubao" in model_lower or "seedream" in model_lower:
        return "1792x1024" if size == "wide" else "1024x1024"

    # 默认
    return "1024x576" if size == "wide" else "1024x1024"


def _call_image_api(api_key: str, api_base: str, model: str,
                    prompt: str, size_param: str) -> Dict:
    """调用图像生成 API，返回标准化的结果"""
    api_base = api_base.rstrip("/")

    # 构建完整的 API URL
    # 如果 api_base 已经包含 /images/generations，直接使用
    if api_base.endswith("/images/generations"):
        image_url = api_base
    elif api_base.endswith("/v1") or api_base.endswith("/v4"):
        image_url = f"{api_base}/images/generations"
    else:
        image_url = f"{api_base}/v1/images/generations"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size_param,
    }

    # DALL-E 3 特有参数
    if "dall-e" in model.lower():
        payload["quality"] = "hd"
        payload["response_format"] = "url"

    resp = requests.post(image_url, headers=headers, json=payload, timeout=120)

    if resp.status_code != 200:
        error_msg = f"API 返回 HTTP {resp.status_code}"
        try:
            error_data = resp.json()
            if "error" in error_data:
                err = error_data["error"]
                error_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        except Exception:
            error_msg = resp.text[:300]
        return {"ok": False, "error": error_msg}

    data = resp.json()
    images = data.get("data", [])

    if not images:
        return {"ok": False, "error": "API 未返回图像数据"}

    image_data = images[0]
    remote_url = image_data.get("url", "")
    b64_data = image_data.get("b64_json", "")

    # 下载或解码图片
    timestamp = int(time.time())
    filename = f"cover_{timestamp}.png"
    local_path = OUTPUT_DIR / filename

    if remote_url:
        img_resp = requests.get(remote_url, timeout=60)
        if img_resp.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(img_resp.content)
        else:
            return {"ok": False, "error": "下载生成的图片失败"}
    elif b64_data:
        img_bytes = base64.b64decode(b64_data)
        with open(local_path, "wb") as f:
            f.write(img_bytes)
    else:
        return {"ok": False, "error": "API 未返回有效的图像数据"}

    # 保存 prompt 记录
    meta_path = OUTPUT_DIR / f"cover_{timestamp}_meta.json"
    meta = {
        "title": "",
        "style": "",
        "size": "",
        "prompt": prompt,
        "filename": filename,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "image_url": f"/api/cover_maker/image/{filename}",
        "image_path": str(local_path),
        "filename": filename,
        "prompt": prompt,
        "revised_prompt": image_data.get("revised_prompt", ""),
    }


def generate_cover(
    title: str,
    content: str = "",
    style: str = "minimal",
    size: str = "wide",
    custom_prompt: str = "",
    user_id: int = None,
) -> Dict:
    """
    生成微信公众号封面

    Args:
        title: 文章标题
        content: 文章内容摘要（可选）
        style: 风格预设 (minimal/tech/warm/nature/abstract/news/food/city)
        size: 尺寸 (wide/square)
        custom_prompt: 自定义图像描述（覆盖风格预设）
        user_id: 用户ID

    Returns:
        {"ok": True, "image_url": "...", ...} 或 {"ok": False, "error": "..."}
    """
    config = _get_cover_config(user_id)
    api_key = config.get("api_key", "")
    api_base = config.get("api_base", "")
    model = config.get("model", "")

    if not api_key:
        # 生成友好的配置指引
        providers_hint = "、".join(
            f"{v['name']}({v['doc']})" for v in IMAGE_PROVIDERS.values()
        )
        return {
            "ok": False,
            "error": (
                "未配置图像生成 API。请选择以下任一服务商注册获取 API Key，"
                "然后在系统配置中填写：\n\n"
                f"{providers_hint}\n\n"
                "配置方式：设置环境变量 COVER_API_KEY（和 COVER_API_BASE、COVER_MODEL），"
                "或在系统配置的 AI 模型管理中配置封面生成专用 API。"
            ),
        }

    if not api_base:
        api_base = "https://api.siliconflow.cn/v1"

    if not model:
        model = "black-forest-labs/FLUX.1-schnell"

    # 构建 prompt
    prompt = _build_image_prompt(title, content, style, custom_prompt)

    # 确定尺寸参数
    size_param = _determine_size_param(size, model)

    try:
        result = _call_image_api(api_key, api_base, model, prompt, size_param)

        # 保存到数据库
        if result.get("ok") and user_id:
            try:
                from modules.user_db import UserDB
                with UserDB() as db:
                    db.conn.execute(
                        """
                        INSERT INTO cover_generations (
                            user_id, title, content, style, size, custom_prompt,
                            filename, image_url, prompt, revised_prompt, model
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            title[:100],
                            content[:200],
                            style,
                            size,
                            custom_prompt[:500],
                            result.get("filename", ""),
                            result.get("image_url", ""),
                            prompt,
                            result.get("revised_prompt", ""),
                            model,
                        )
                    )
                    db.conn.commit()
            except Exception as e:
                print(f"[cover_maker] 保存封面记录到数据库失败：{e}")

            # 兼容旧逻辑：更新本地 meta json（如果存在）
            try:
                meta_path = OUTPUT_DIR / f"cover_{int(time.time())}_meta.json"
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    meta["title"] = title[:100]
                    meta["style"] = style
                    meta["size"] = size
                    meta["model"] = model
                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(meta, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return result

    except requests.exceptions.Timeout:
        return {"ok": False, "error": "图像生成超时（通常需要 10-30 秒），请稍后重试"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "无法连接到图像生成服务，请检查网络和 API 地址"}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"网络请求失败: {str(e)}"}
    except Exception as e:
        return {"ok": False, "error": f"生成失败: {str(e)}"}


def get_cover_history(user_id: int = None, limit: int = 20) -> List[Dict]:
    """获取封面生成历史（从数据库，支持用户隔离）"""
    # 优先从数据库读取
    if user_id:
        try:
            from modules.user_db import UserDB
            with UserDB() as db:
                cur = db.conn.cursor()
                cur.execute(
                    """
                    SELECT id, title, style, size, filename, image_url, prompt,
                           revised_prompt, model, created_at, is_collected
                    FROM cover_generations
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit)
                )
                rows = cur.fetchall()
                results = []
                for row in rows:
                    item = dict(row)
                    # 检查图片文件是否存在
                    filename = item.get("filename", "")
                    image_path = OUTPUT_DIR / filename
                    if image_path.exists():
                        item["image_url"] = f"/api/cover_maker/image/{filename}"
                        results.append(item)
                return results
        except Exception as e:
            print(f"[cover_maker] 从数据库读取历史失败：{e}")

    # 降级：从文件系统读取（兼容旧数据）
    results = []
    meta_files = sorted(OUTPUT_DIR.glob("cover_*_meta.json"), reverse=True)

    for meta_path in meta_files[:limit]:
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            filename = meta.get("filename", "")
            image_path = OUTPUT_DIR / filename
            if image_path.exists():
                meta["image_url"] = f"/api/cover_maker/image/{filename}"
                results.append(meta)
        except Exception:
            continue

    return results


def delete_cover(filename: str, user_id: int = None) -> bool:
    """删除封面图片和元数据"""
    try:
        image_path = OUTPUT_DIR / filename
        timestamp = filename.replace("cover_", "").replace(".png", "")
        meta_path = OUTPUT_DIR / f"cover_{timestamp}_meta.json"

        if image_path.exists():
            image_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

        # 从数据库删除记录
        if user_id:
            try:
                from modules.user_db import UserDB
                with UserDB() as db:
                    db.conn.execute(
                        "DELETE FROM cover_generations WHERE filename = ? AND user_id = ?",
                        (filename, user_id)
                    )
                    db.conn.commit()
            except Exception as e:
                print(f"[cover_maker] 从数据库删除记录失败：{e}")

        return True
    except Exception:
        return False
