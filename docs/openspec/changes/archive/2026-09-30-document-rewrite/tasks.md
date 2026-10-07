## 1. 依赖与基础

- [x] 1.1 在 requirements.txt 末尾追加 `python-docx>=0.8.11` 和 `pdfplumber>=0.11.0`，运行 `pip install -r requirements.txt` 确认安装成功
- [x] 1.2 创建 `modules/document_parser.py` 文件，定义 `parse_document(file_bytes, filename) -> str` 函数签名和格式路由逻辑

## 2. 文档解析模块

- [x] 2.1 实现 `_parse_docx(file_bytes)` —— 使用 python-docx 提取所有段落文本，以 `\n` 连接。验证：上传测试 .docx 文件返回非空纯文本
- [x] 2.2 实现 `_parse_pdf(file_bytes)` —— 使用 pdfplumber 逐页提取文本，以 `\n\n` 分隔页面。验证：上传测试 .pdf 文件返回非空纯文本
- [x] 2.3 实现 `_parse_text(file_bytes)` —— UTF-8 优先读取，失败降级 latin-1。验证：上传 .md 和 .txt 文件返回原文
- [x] 2.4 实现 `parse_document()` 主函数 —— 根据文件扩展名路由到对应解析器，不支持格式抛出 ValueError，解析失败抛出 RuntimeError。验证：传入各格式文件均正确路由

## 3. 后端 API

- [x] 3.1 在 `web_app.py` 新增 `POST /api/document/parse` 路由 —— 接收 `request.files["file"]`，调用 `parse_document()`，返回 `{"ok": true, "content": "..."}` 或 `{"ok": false, "error": "..."}`。验证：用 curl 上传文件返回解析文本
- [x] 3.2 在 `web_app.py` 新增 `POST /api/document/rewrite` 路由 —— 接收 `content`、`style`、`word_count`、`task_id`、`account_id`，在后台线程中调用 `rewrite_article()` 并通过 `push_log()` SSE 推送进度，完成后推送结果。验证：调用后 SSE 流输出完整文章

## 4. 前端页面

- [x] 4.1 创建 `web_static/document_rewrite.html` —— 包含上传区（拖拽+点击）、解析预览文本框、风格/字数选择、"开始改写"按钮、SSE 日志卡片、文章编辑器区域。引用 `common.js` 和 `agent.css` 保持样式一致。验证：页面在浏览器中正常加载
- [x] 4.2 创建 `web_static/document_rewrite.js` —— 实现文件选择/拖拽上传、调用 `/api/document/parse`、填充预览框、调用 `/api/document/rewrite` 并订阅 SSE 日志、完成后填充编辑器。验证：端到端流程跑通

## 5. 导航集成

- [x] 5.1 在 `web_static/common.js` 的 `switchPage()` 的 `titles` 对象中新增 `document_rewrite: '📄 文档改写'`。验证：侧边栏出现菜单项且标题切换正确
- [x] 5.2 在 `dashboard.html` 的侧边栏 nav 列表中添加文档改写入口，并在 web_app.py 添加 `/document_rewrite.html` 和 `/document_rewrite.js` 路由。验证：点击侧边栏切换到文档改写页面

## 6. 端到端验证

- [x] 6.1 完整流程测试：启动应用 → 侧边栏点击"文档改写" → 上传 .docx → 解析预览确认 → 选择风格字数 → 点击改写 → SSE 日志滚动 → 文章填入编辑器 → 预览正常。验证：全流程无报错
- [x] 6.2 边界测试：上传不支持格式 → 显示错误；上传超大文件 → 显示错误；解析空内容后点改写 → 提示为空。验证：各边界场景正确拦截
