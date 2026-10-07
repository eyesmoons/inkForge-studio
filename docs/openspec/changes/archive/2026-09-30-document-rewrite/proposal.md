## Why

现有"一键写稿"功能仅支持从热搜选题生成文章，但用户经常已有初稿文档（调研报告、会议纪要、技术文档等），需要将其改写为适合公众号发布的文章。当前没有文档导入入口，用户只能手动复制粘贴内容，体验割裂且效率低。

## What Changes

- 新增前端页面 `document_rewrite.html` + `document_rewrite.js`，提供文档上传、解析预览、改写生成完整工作流
- 新增侧边栏导航入口"📄 文档改写"，与现有"一键写稿"并列
- 新增后端文档解析模块 `modules/document_parser.py`，支持 .docx / .pdf / .md / .txt 四种格式
- 新增 API 路由 `/api/document/parse`（文档解析）和 `/api/document/rewrite`（改写生成）
- 复用现有 `modules/article_rewriter.py` 的 AI 改写能力和 SSE 日志流
- 新增 Python 依赖：`python-docx`、`pdfplumber`

## Capabilities

### New Capabilities

- `document-upload`: 文件上传与格式校验（支持 .docx/.pdf/.md/.txt，10MB 限制）
- `document-parsing`: 文档内容解析为纯文本（提取段落结构，不含图片/表格）
- `document-rewrite-workflow`: 文档改写工作流（解析→预览编辑→配置→SSE流式生成→编辑器预览）

### Modified Capabilities

（无现有 capability 的需求变更）

## Impact

- **新增文件**：`web_static/document_rewrite.html`、`web_static/document_rewrite.js`、`modules/document_parser.py`
- **修改文件**：`web_app.py`（新增 2 个 API 路由）、`web_static/common.js`（侧边栏新增菜单项）、`requirements.txt`（新增依赖）
- **复用模块**：`modules/article_rewriter.py`（AI 改写）、`common.js` 的 `subscribeSSE`（日志流）、`md_converter.py`（预览转换）
- **新增依赖**：`python-docx>=0.8.11`、`pdfplumber>=0.11.0`
