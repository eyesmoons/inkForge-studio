## Context

现有系统已有完整的文件上传（`material_library` 模块的 `FormData` + `request.files` 模式）、SSE 流式日志（`subscribeSSE` + `QueueLogger`）、AI 改写（`modules/article_rewrite.py` 的 `rewrite_article()`）能力。本功能在此基础上新增文档解析层和前端工作流页面。

## Goals / Non-Goals

**Goals:**
- 新增独立前端页面，提供文档上传→解析预览→改写生成的完整工作流
- 新增后端文档解析模块，支持 docx/pdf/md/txt 四种格式
- 复用现有 AI 改写和 SSE 日志流，保持架构一致

**Non-Goals:**
- 不解析文档中的图片、表格等富媒体内容
- 不支持批量上传或多文件合并
- 不保存上传的原始文档到数据库或磁盘（仅临时读取后丢弃）

## Decisions

### 文档解析库选型

**选择：** `python-docx` + `pdfplumber`

**备选：**
- `PyPDF2` — 纯 PDF 提取够用，但表格和复杂排版支持较弱
- `markitdown`（微软开源）— 统一多格式解析，但引入较重依赖

**Rationale:** python-docx 和 pdfplumber 各自是领域最成熟方案，依赖轻量、API 简单，满足纯文本提取需求。pdfplumber 在 PDF 文本保留上优于 PyPDF2。

### 前后端通信模式

**选择：** 沿用现有 `FormData` + Flask `request.files` 模式，与素材库上传保持一致

**Rationale:** 项目已有成熟实现（`material_library.js` 的 `handleUploadFile` + `web_app.py` 的 `api_upload_material`），无需引入新的通信协议。

### 页面架构

**选择：** 独立 HTML 页面 `document_rewrite.html` + `document_rewrite.js`，SPA 侧边栏导航

**备选：** 嵌入现有 `write.html` 页面作为子选项卡

**Rationale:** 独立页面与 `cover_maker.html`、`hotrank.html` 模式一致，工作流独立清晰，不增加 write.html 复杂度。侧边栏已在 `common.js` 的 `switchPage` 中支持扩展。

### 解析与改写分离

**选择：** 后端分为 `/api/document/parse`（解析）和 `/api/document/rewrite`（改写）两个独立 API

**Rationale:** 解耦解析和生成步骤，用户在中间环节可以预览和编辑。两个 API 各自职责单一，便于调试和维护。

## Risks / Trade-offs

- **PDF 解析质量参差** → pdfplumber 对扫描件/图片型 PDF 无法提取文字。Mitigation：前端提示"扫描版 PDF 无法提取文字，请使用可复制文本的 PDF"
- **大文档解析耗时** → 超长文档（10MB+）可能解析缓慢。Mitigation：限制 10MB 上限；解析在后端线程中进行不阻塞请求
- **编码兼容性** → 老旧 .txt 文件可能使用 GBK 编码。Mitigation：UTF-8 优先，失败时降级 latin-1
