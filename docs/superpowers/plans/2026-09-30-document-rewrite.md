---
change: document-rewrite
design-doc: docs/superpowers/specs/2026-09-30-document-rewrite-design.md
base-ref: 0eed7681f41e749698d33a35425249eae1326445
archived-with: 2026-09-30-document-rewrite
---

# 文档改写功能 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许用户上传 Word/PDF/Markdown/纯文本文档，解析为纯文本后调用 AI 改写模块生成公众号文章。

**Architecture:** 新增 `modules/document_parser.py` 处理多格式文档解析；在 `web_app.py` 新增两个 REST 路由（parse + rewrite）；新增 `web_static/document_rewrite.html` + `document_rewrite.js` 前端页面；通过现有 SSE 日志流推送改写进度。改写复用 `modules/article_rewriter.rewrite_article()`。

**Tech Stack:** Flask (路由)、python-docx (Word 解析)、pdfplumber (PDF 解析)、vanilla JS (前端)、SSE (日志流)

**Spec:** docs/superpowers/specs/2026-09-30-document-rewrite-design.md

## Global Constraints

- 文件格式白名单仅 `.docx` `.pdf` `.md` `.txt`，不依赖 MIME type
- 文件大小限制 10MB，防止内存耗尽
- 文件不落盘，二进制数据仅在请求内存中处理
- 所有 API 校验 session_id，未登录返回 401
- 前端使用 textContent / value 填充内容，不直接 innerHTML（XSS 防护）
- 语言：zh-CN
- 遵循现有代码风格：模块文件顶部 docstring、try/except 显式异常类型、路由返回 `jsonify({ok: true/false, ...})`

---

## 1. 依赖与基础

- [x] 1.1 在 requirements.txt 末尾追加 `python-docx>=0.8.11` 和 `pdfplumber>=0.11.0`，运行 `pip install -r requirements.txt` 确认安装成功

在 requirements.txt 末尾追加：
```
# 文档解析（Word/PDF）
python-docx>=0.8.11
pdfplumber>=0.11.0
```

运行 `pip install "python-docx>=0.8.11" "pdfplumber>=0.11.0"` 并验证 `python -c "import docx; import pdfplumber; print('OK')"`。

- [x] 1.2 创建 `modules/document_parser.py` 文件，定义 `parse_document(file_bytes, filename) -> str` 函数签名和格式路由逻辑

创建文件骨架，包含 ALLOWED_EXTENSIONS、MAX_FILE_SIZE 常量，parse_document 主函数（格式路由 + 错误处理），以及 _parse_docx、_parse_pdf、_parse_text 三个私有函数。

---

## 2. 文档解析模块

- [x] 2.1 实现 `_parse_docx(file_bytes)` —— 使用 python-docx 提取所有段落文本，以 `\n` 连接。验证：上传测试 .docx 文件返回非空纯文本

```python
def _parse_docx(file_bytes: bytes) -> str:
    import docx
    doc = docx.Document(BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return '\n'.join(paragraphs)
```

- [x] 2.2 实现 `_parse_pdf(file_bytes)` —— 使用 pdfplumber 逐页提取文本，以 `\n\n` 分隔页面。验证：上传测试 .pdf 文件返回非空纯文本

```python
def _parse_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    pages_text = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())
    return '\n\n'.join(pages_text)
```

- [x] 2.3 实现 `_parse_text(file_bytes)` —— UTF-8 优先读取，失败降级 latin-1。验证：上传 .md 和 .txt 文件返回原文

```python
def _parse_text(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return file_bytes.decode('latin-1')
```

- [x] 2.4 实现 `parse_document()` 主函数 —— 根据文件扩展名路由到对应解析器，不支持格式抛出 ValueError，解析失败抛出 RuntimeError。验证：传入各格式文件均正确路由

验证：
```bash
python -c "
from modules.document_parser import parse_document
r = parse_document(b'hello', 'test.txt')
assert r == 'hello'
try:
    parse_document(b'x', 'file.xlsx')
    assert False
except ValueError:
    pass
print('OK')
"
```

---

## 3. 后端 API

- [x] 3.1 在 `web_app.py` 新增 `POST /api/document/parse` 路由 —— 接收 `request.files["file"]`，调用 `parse_document()`，返回 `{"ok": true, "content": "..."}` 或 `{"ok": false, "error": "..."}`。验证：用 curl 上传文件返回解析文本

在 web_app.py QueueLogger 类之后插入 parse 路由（参考现有 api_upload_material 模式）。

- [x] 3.2 在 `web_app.py` 新增 `POST /api/document/rewrite` 路由 —— 接收 `content`、`style`、`word_count`、`task_id`、`account_id`，在后台线程中调用 `rewrite_article()` 并通过 `push_log()` SSE 推送进度，完成后推送结果。验证：调用后 SSE 流输出完整文章

紧跟 parse 路由之后插入 rewrite 路由。注意：
- word_count 服务端校验范围 500-10000
- content 长度限制 100KB
- SSE 结果格式为 {"md_content": result, ...}
- 完成后清理 _log_queues[task_id]

---

## 4. 前端页面

- [x] 4.1 创建 `web_static/document_rewrite.html` —— 包含上传区（拖拽+点击）、解析预览文本框、风格/字数选择、"开始改写"按钮、SSE 日志卡片、文章编辑器区域。引用 `common.js` 和 `agent.css` 保持样式一致。验证：页面在浏览器中正常加载

参考 today_in_history.html 的侧边栏结构，创建独立页面。包含结果预览区（dr-result-section）。

- [x] 4.2 创建 `web_static/document_rewrite.js` —— 实现文件选择/拖拽上传、调用 `/api/document/parse`、填充预览框、调用 `/api/document/rewrite` 并订阅 SSE 日志、完成后填充编辑器。验证：端到端流程跑通

实现状态机（idle → file_selected → parsing → preview → rewriting → done），完成后显示结果预览区。

---

## 5. 导航集成

- [x] 5.1 在 `web_static/common.js` 的 `switchPage()` 的 `titles` 对象中新增 `document_rewrite: '📄 文档改写'`。验证：侧边栏出现菜单项且标题切换正确

- [x] 5.2 在 `dashboard.html` 的侧边栏 nav 列表中添加文档改写入口，并在 web_app.py 添加 `/document_rewrite.html` 和 `/document_rewrite.js` 路由。验证：点击侧边栏切换到文档改写页面

dashboard.html 在 /import.html 之后添加 nav 项。web_app.py 在 material_library_page 之后添加路由。

---

## 6. 端到端验证

- [x] 6.1 完整流程测试：启动应用 → 侧边栏点击"文档改写" → 上传 .docx → 解析预览确认 → 选择风格字数 → 点击改写 → SSE 日志滚动 → 文章填入编辑器 → 预览正常。验证：全流程无报错

- [x] 6.2 边界测试：上传不支持格式 → 显示错误；上传超大文件 → 显示错误；解析空内容后点改写 → 提示为空。验证：各边界场景正确拦截

```bash
python -c "
from modules.document_parser import parse_document
r = parse_document(b'hello', 'test.txt')
assert r == 'hello'
try:
    parse_document(b'x', 'file.xlsx')
    assert False
except ValueError:
    pass
print('All tests passed')
"
```

---

## 文件变更清单总结

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `requirements.txt` | +python-docx, +pdfplumber |
| 创建 | `modules/document_parser.py` | 文档解析核心模块 |
| 修改 | `web_app.py` | +2 API 路由, +1 页面路由 |
| 创建 | `web_static/document_rewrite.html` | 页面骨架 + 样式 |
| 创建 | `web_static/document_rewrite.js` | 交互逻辑 |
| 修改 | `web_static/common.js` | +1 switchPage title |
| 修改 | `web_static/dashboard.html` | +1 侧边栏 nav 项 |
