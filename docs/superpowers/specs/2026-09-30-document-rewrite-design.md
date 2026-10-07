---
comet_change: document-rewrite
role: technical-design
canonical_spec: openspec
archived-with: 2026-09-30-document-rewrite
status: final
---

# 文档改写功能 — 技术设计文档

## 1. 概述

本设计细化 document-rewrite change 的技术实现方案。该功能允许用户上传 Word/PDF/Markdown/纯文本文档，解析为纯文本后调用 AI 改写模块生成公众号文章。

## 2. 架构设计

### 2.1 系统上下文

```
┌─────────────────────────────────────────────────────────────────┐
│                         浏览器 (前端)                            │
│                                                                 │
│  document_rewrite.html + document_rewrite.js                    │
│       │                                                         │
│       ├── FormData 上传 ──→ POST /api/document/parse            │
│       ├── JSON 提交   ──→ POST /api/document/rewrite            │
│       └── SSE 订阅    ←── /api/logs/<task_id>                   │
└───────┼─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Flask 后端 (web_app.py)                      │
│                                                                 │
│  /api/document/parse  ──→ modules/document_parser.py            │
│                            └── parse_document(bytes, filename)  │
│                                                                 │
│  /api/document/rewrite ──→ 后台线程                             │
│                            └── rewrite_article()                │
│                                └── _call_llm()                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  上传    │────▶│  解析    │────▶│  改写    │────▶│  预览    │
│  文档    │     │  预览    │     │  生成    │     │  发布    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
     │                │                │                │
     ▼                ▼                ▼                ▼
  FormData       纯文本         Markdown         HTML 预览
  /api/parse      可编辑         SSE 流式         草稿箱
```

## 3. 模块设计

### 3.1 `modules/document_parser.py` — 文档解析

```python
"""文档解析模块：将不同格式文档统一转换为纯文本"""

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
            return _parse_pdf(file_bytes)
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


def _parse_text(file_bytes: bytes) -> str:
    """Markdown / 纯文本解析：UTF-8 优先，latin-1 降级"""
    try:
        return file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return file_bytes.decode('latin-1')
```

### 3.2 `web_app.py` — API 路由

新增两个路由，插入在现有 SSE 日志路由之后：

```python
@app.route("/api/document/parse", methods=["POST"])
def api_document_parse():
    """解析上传的文档为纯文本"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"ok": False, "error": "请先登录"}), 401

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "未选择文件"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "未选择文件"}), 400

    try:
        from modules.document_parser import parse_document
        content = parse_document(file.read(), file.filename)
        return jsonify({"ok": True, "content": content})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 422


@app.route("/api/document/rewrite", methods=["POST"])
def api_document_rewrite():
    """将文档内容改写为公众号文章（SSE 流式）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    content = (data.get("content") or "").strip()
    style = data.get("style", "观点评论")
    word_count = data.get("word_count", 2000)
    task_id = data.get("task_id", str(uuid.uuid4()))
    account_id = (data.get("account_id") or "").strip()

    if not content:
        return jsonify({"error": "内容为空"}), 400
    if not account_id:
        return jsonify({"error": "请选择账号"}), 400

    acc_cfg = get_account_config(account_id)
    if not acc_cfg:
        return jsonify({"error": "账号配置不存在"}), 400

    current_user_id = user["id"]
    _log_queues[task_id] = queue.Queue()

    def run():
        orig = sys.stdout
        sys.stdout = QueueLogger(task_id, orig)
        try:
            from modules.article_rewriter import rewrite_article
            result = rewrite_article(
                original_title="文档改写",
                original_content=content,
                user_id=current_user_id,
                word_count=word_count,
                style=style,
            )
            push_log(task_id, json.dumps({
                "msg": "__DONE__",
                "level": "done",
                "result": {"md_content": result}
            }), "result")
        except Exception as e:
            push_log(task_id, f"❌ 改写失败：{traceback.format_exc()}", "error")
        finally:
            sys.stdout = orig
            _log_queues[task_id].put(None)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})
```

### 3.3 `web_static/document_rewrite.js` — 前端逻辑

核心状态机：

```javascript
const DR = {
  state: 'idle',        // idle | file_selected | parsing | preview | rewriting | done
  currentFile: null,
  parsedContent: '',
};

function onFileSelected(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  const allowed = ['.docx', '.pdf', '.md', '.txt'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    toast('不支持的文件格式，请使用 .docx/.pdf/.md/.txt', 'error');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    toast('文件大小不能超过 10MB', 'error');
    return;
  }
  DR.currentFile = file;
  DR.state = 'file_selected';
  updateUI();
}

async function parseDocument() {
  if (!DR.currentFile) return;
  DR.state = 'parsing';
  updateUI();
  const formData = new FormData();
  formData.append('file', DR.currentFile);
  try {
    const resp = await fetch('/api/document/parse', { method: 'POST', body: formData });
    const data = await resp.json();
    if (data.ok) {
      DR.parsedContent = data.content;
      DR.state = 'preview';
      document.getElementById('dr-preview-textarea').value = data.content;
    } else {
      toast(data.error || '解析失败', 'error');
      DR.state = 'file_selected';
    }
  } catch (e) {
    toast('网络错误', 'error');
    DR.state = 'file_selected';
  }
  updateUI();
}

async function startRewrite() {
  const content = document.getElementById('dr-preview-textarea').value.trim();
  if (!content) {
    toast('内容为空，请先上传文档或输入文字', 'error');
    return;
  }
  DR.state = 'rewriting';
  updateUI();
  const taskId = uuid();
  const style = document.getElementById('dr-style').value;
  const wordCount = parseInt(document.getElementById('dr-wordcount').value);
  const accountId = document.getElementById('account-selector').value;
  try {
    const resp = await fetch('/api/document/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content, style, word_count: wordCount,
        task_id: taskId, account_id: accountId,
      }),
    });
    const data = await resp.json();
    if (!data.ok) {
      toast(data.error || '启动改写失败', 'error');
      DR.state = 'preview';
      updateUI();
      return;
    }
    const logEl = document.getElementById('dr-log');
    subscribeSSE(taskId, logEl, (result) => {
      if (result.md_content) {
        document.getElementById('md-editor').value = result.md_content;
        DR.state = 'done';
        updateUI();
        switchPage('write', document.querySelector('[data-page=write]'));
        previewMarkdown();
        toast('文章生成完成！', 'success');
      }
    });
  } catch (e) {
    toast('网络错误', 'error');
    DR.state = 'preview';
    updateUI();
  }
}
```

## 4. 错误处理

| 错误场景 | 前端行为 | 后端响应 |
|----------|----------|----------|
| 不支持的文件格式 | 上传前拦截 toast | 400 + 错误信息 |
| 文件超过 10MB | 上传前拦截 toast | 400 + 错误信息 |
| 文档损坏无法解析 | 显示错误 toast | 422 + 错误信息 |
| AI 模型未配置 | SSE 推送错误日志 | SSE error 级别 |
| LLM 调用失败 | SSE 推送异常信息 | SSE error 级别 |
| 网络超时 | 显示网络错误 toast | — |
| 内容为空提交改写 | 前端拦截 toast | 400 + 错误信息 |

## 5. 安全考虑

- **文件格式白名单**：仅允许 `.docx/.pdf/.md/.txt`，不依赖 MIME type（易伪造）
- **大小限制**：10MB，防止内存耗尽
- **文件不落盘**：二进制数据仅在请求内存中处理，解析后立即释放
- **用户认证**：所有 API 校验 session_id，未登录返回 401
- **XSS 防护**：前端使用 textContent / value 填充内容，不直接 innerHTML

## 6. 前端页面结构

```html
<div class="dr-container">
  <!-- 步骤指示器 -->
  <div class="dr-steps">
    <div class="dr-step active">① 上传文档</div>
    <div class="dr-step">② 预览确认</div>
    <div class="dr-step">③ 改写生成</div>
    <div class="dr-step">④ 预览发布</div>
  </div>

  <!-- 步骤 1: 上传 -->
  <div id="dr-upload-section">
    <div id="dr-drop-zone" class="dr-drop-zone">
      <p>📎 点击或拖拽文件到此处</p>
      <p class="dr-hint">支持 .docx .pdf .md .txt，最大 10MB</p>
      <input type="file" id="dr-file-input" accept=".docx,.pdf,.md,.txt" hidden>
    </div>
    <div id="dr-file-info" style="display:none">
      <span id="dr-filename"></span>
      <button onclick="parseDocument()" class="btn btn-primary">解析文档</button>
    </div>
  </div>

  <!-- 步骤 2: 预览编辑 -->
  <div id="dr-preview-section" style="display:none">
    <textarea id="dr-preview-textarea" class="dr-textarea"></textarea>
    <div class="dr-options">
      <select id="dr-style"><!-- 风格选项 --></select>
      <input type="number" id="dr-wordcount" value="2000" min="500" max="10000">
    </div>
    <button onclick="startRewrite()" class="btn btn-primary">✨ 开始改写</button>
  </div>

  <!-- 步骤 3: 日志 -->
  <div id="dr-log-section" style="display:none">
    <div id="dr-log" class="dr-log"></div>
  </div>
</div>
```

## 7. 文件变更清单

### 新增文件
| 文件 | 行数（估计） | 职责 |
|------|-------------|------|
| `modules/document_parser.py` | ~60 | 文档解析核心逻辑 |
| `web_static/document_rewrite.html` | ~80 | 页面骨架 + 样式 |
| `web_static/document_rewrite.js` | ~120 | 交互逻辑 |

### 修改文件
| 文件 | 变更点 |
|------|--------|
| `web_app.py` | +2 个路由（parse + rewrite），+2 个 import |
| `web_static/common.js` | +1 菜单项 + 支持 switchPage('document_rewrite') |
| `web_static/dashboard.html` | +nav item + page container |
| `requirements.txt` | +python-docx + pdfplumber |

## 8. 测试策略

### 单元测试（手动验证清单）

- [ ] `parse_document()` 传入 .docx 返回非空段落文本
- [ ] `parse_document()` 传入 .pdf 返回非空页面文本
- [ ] `parse_document()` 传入 .md 返回原文
- [ ] `parse_document()` 传入 .txt (UTF-8) 返回原文
- [ ] `parse_document()` 传入 .txt (latin-1) 正常解码
- [ ] `parse_document()` 传入不支持格式抛出 ValueError
- [ ] `parse_document()` 传入损坏 docx 抛出 RuntimeError

### API 集成测试（curl）

```bash
curl -X POST http://localhost:5000/api/document/parse \
  -F "file=@test.docx" \
  -H "X-Session-Id: <session>"

curl -X POST http://localhost:5000/api/document/rewrite \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: <session>" \
  -d '{"content":"测试内容","style":"深度科普","word_count":2000,"task_id":"test-1","account_id":"default"}'
```

### E2E 测试（浏览器）

- [ ] 完整流程：上传 → 解析 → 编辑 → 改写 → SSE 日志 → 编辑器填充 → 预览正常
- [ ] 拖拽上传正常
- [ ] 不支持格式提示正确
- [ ] 超大文件提示正确
- [ ] 空内容拦截正确

## 9. 实现顺序

1. **依赖安装** → requirements.txt + pip install
2. **后端解析** → document_parser.py + 单元测试
3. **后端 API** → web_app.py 两个路由 + curl 测试
4. **前端页面** → HTML + CSS + JS
5. **导航集成** → common.js + dashboard.html
6. **E2E 验证** → 浏览器完整流程

## 10. 开放问题

无。所有技术决策已在设计阶段确认，实现阶段无歧义。
