"""文档解析模块：将不同格式文档统一转换为纯文本

支持格式：.docx (Word)、.pdf、.md (Markdown)、纯文本 (.txt)
PDF 解析失败时会使用 AI 视觉读取（需要配置支持多模态的 AI 模型）
"""

from pathlib import Path
from io import BytesIO

ALLOWED_EXTENSIONS = {'.docx', '.pdf', '.md', '.txt'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def parse_document(file_bytes: bytes, filename: str) -> str:
    """
    根据文件扩展名路由到对应解析器。

    Args:
        file_bytes: 文件二进制内容
        filename: 原始文件名（用于判断扩展名）

    Returns:
        解析后的纯文本字符串

    Raises:
        ValueError: 不支持的文件格式或文件过大
        RuntimeError: 解析失败
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError("文件大小不能超过 10MB")

    try:
        if ext == '.docx':
            return _parse_docx(file_bytes)
        elif ext == '.pdf':
            return _parse_pdf_with_fallback(file_bytes)
        elif ext in ('.md', '.txt'):
            return _parse_text(file_bytes)
    except (ValueError, RuntimeError):
        raise
    except Exception as e:
        raise RuntimeError(f"文档解析失败: {e}")


def _parse_docx(file_bytes: bytes) -> str:
    """Word 文档解析：提取所有段落文本"""
    import docx
    doc = docx.Document(BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return '\n'.join(paragraphs)


def _parse_pdf_with_fallback(file_bytes: bytes) -> str:
    """PDF 解析：优先使用 pdfplumber，失败时回退到 AI 视觉读取"""
    # 尝试 pdfplumber 快速提取
    try:
        text = _parse_pdf(file_bytes)
        if text.strip():
            return text
    except Exception:
        pass

    # pdfplumber 失败或返回空文本，尝试 AI 视觉读取
    try:
        return _parse_pdf_with_ai(file_bytes)
    except Exception as e:
        raise RuntimeError(
            f"PDF 解析失败（pdfplumber 和 AI 读取均不可用）：{e}\n"
            "建议：上传 Word (.docx) 或 Markdown (.md) 格式，或确保 PDF 包含可复制文本"
        )


def _parse_pdf(file_bytes: bytes) -> str:
    """PDF 文档解析：逐页提取文本"""
    import pdfplumber
    pages_text = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())
    return '\n\n'.join(pages_text)


def _parse_pdf_with_ai(file_bytes: bytes) -> str:
    """使用 AI 视觉读取 PDF（适用于扫描版/图片型 PDF）"""
    try:
        from modules.ai_writer import _detect_llm_backend, _call_openai, _call_ollama
    except ImportError:
        raise RuntimeError("AI 模块不可用")

    backend, config = _detect_llm_backend()

    # 将 PDF 转换为图片
    try:
        import pdfplumber
        from PIL import Image
        pages = []
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                # 将页面转换为图片 (dpi=200 保证清晰度)
                img = page.to_image(resolution=200)
                pages.append(img.original)
    except Exception as e:
        raise RuntimeError(f"PDF 转图片失败：{e}")

    if not pages:
        raise RuntimeError("PDF 没有可读取的页面")

    # 构建多模态消息
    all_text = []
    for i, pil_image in enumerate(pages):
        # 将 PIL 图片转为 base64
        buf = BytesIO()
        pil_image.save(buf, format='JPEG', quality=85)
        import base64
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        prompt = (
            f"这是 PDF 的第 {i+1} 页（共 {len(pages)} 页）。"
            "请准确识别并提取页面中的所有文字内容，保持原始段落结构。"
            "只返回提取的文本，不要添加任何解释或总结。"
        )

        if backend == "openai":
            text = _call_openai_vision(prompt, img_base64, config)
        elif backend == "ollama":
            text = _call_ollama_vision(prompt, img_base64, config)
        else:
            raise RuntimeError(f"不支持的 AI 后端：{backend}")

        if text.strip():
            all_text.append(text.strip())

    if not all_text:
        raise RuntimeError("AI 未能从 PDF 中识别出文字")

    return '\n\n'.join(all_text)


def _call_openai_vision(prompt: str, image_base64: str, config: dict) -> str:
    """调用 OpenAI 视觉 API"""
    url = f"{config['api_base'].rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.get("model", "gpt-4o"),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4000,
    }
    import requests
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_ollama_vision(prompt: str, image_base64: str, config: dict) -> str:
    """调用 Ollama 视觉 API（需要多模态模型如 llava）"""
    url = f"{config.get('api_base', 'http://localhost:11434').rstrip('/')}/api/chat"
    payload = {
        "model": config.get("model", "llama3.2-vision"),
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64]
            }
        ],
        "stream": False,
    }
    import requests
    resp = requests.post(url, json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _parse_text(file_bytes: bytes) -> str:
    """Markdown / 纯文本解析：UTF-8 优先，latin-1 降级"""
    try:
        return file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return file_bytes.decode('latin-1')
