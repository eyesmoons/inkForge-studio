# Comet Design Handoff

- Change: document-rewrite
- Phase: design
- Mode: compact
- Context hash: 4dcfe63f153286084f0aacc9369247793a5ad431b29b4c412ed02b552cc7a935

Generated-by: comet-handoff.sh
Task hash policy: task-content-v1. Read tasks.md for live completion; excerpts are design-time context.

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## docs/openspec/changes/document-rewrite/proposal.md

- Source: docs/openspec/changes/document-rewrite/proposal.md
- Lines: 1-31
- SHA256: 6de0ea49a7c6b4aaa54295c33e67ab768c47a1c669f59cbd46c1d951e14bce9d

```md
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

```

## docs/openspec/changes/document-rewrite/design.md

- Source: docs/openspec/changes/document-rewrite/design.md
- Lines: 1-53
- SHA256: 6a2a45468572522fbe1096911af04857d76e8970e37ef11293b33727a7f27339

```md
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

```

## docs/openspec/changes/document-rewrite/tasks.md

- Source: docs/openspec/changes/document-rewrite/tasks.md
- Lines: 1-31
- SHA256: dae5947a4e889c18113ccd7a4c5f7327f1d860689cf3a0161a5d58105187997b

```md
## 1. 依赖与基础

- [ ] 1.1 在 requirements.txt 末尾追加 `python-docx>=0.8.11` 和 `pdfplumber>=0.11.0`，运行 `pip install -r requirements.txt` 确认安装成功
- [ ] 1.2 创建 `modules/document_parser.py` 文件，定义 `parse_document(file_bytes, filename) -> str` 函数签名和格式路由逻辑

## 2. 文档解析模块

- [ ] 2.1 实现 `_parse_docx(file_bytes)` —— 使用 python-docx 提取所有段落文本，以 `\n` 连接。验证：上传测试 .docx 文件返回非空纯文本
- [ ] 2.2 实现 `_parse_pdf(file_bytes)` —— 使用 pdfplumber 逐页提取文本，以 `\n\n` 分隔页面。验证：上传测试 .pdf 文件返回非空纯文本
- [ ] 2.3 实现 `_parse_text(file_bytes)` —— UTF-8 优先读取，失败降级 latin-1。验证：上传 .md 和 .txt 文件返回原文
- [ ] 2.4 实现 `parse_document()` 主函数 —— 根据文件扩展名路由到对应解析器，不支持格式抛出 ValueError，解析失败抛出 RuntimeError。验证：传入各格式文件均正确路由

## 3. 后端 API

- [ ] 3.1 在 `web_app.py` 新增 `POST /api/document/parse` 路由 —— 接收 `request.files["file"]`，调用 `parse_document()`，返回 `{"ok": true, "content": "..."}` 或 `{"ok": false, "error": "..."}`。验证：用 curl 上传文件返回解析文本
- [ ] 3.2 在 `web_app.py` 新增 `POST /api/document/rewrite` 路由 —— 接收 `content`、`style`、`word_count`、`task_id`、`account_id`，在后台线程中调用 `rewrite_article()` 并通过 `push_log()` SSE 推送进度，完成后推送 `{"msg": "__DONE__", "result": {"md_content": "..."}}`。验证：调用后 SSE 流输出完整文章

## 4. 前端页面

- [ ] 4.1 创建 `web_static/document_rewrite.html` —— 包含上传区（拖拽+点击）、解析预览文本框、风格/字数选择、"开始改写"按钮、SSE 日志卡片、文章编辑器区域。引用 `common.js` 和 `agent.css` 保持样式一致。验证：页面在浏览器中正常加载
- [ ] 4.2 创建 `web_static/document_rewrite.js` —— 实现文件选择/拖拽上传、调用 `/api/document/parse`、填充预览框、调用 `/api/document/rewrite` 并订阅 SSE 日志、完成后填充编辑器。验证：端到端流程跑通

## 5. 导航集成

- [ ] 5.1 在 `web_static/common.js` 的 `switchPage()` 的 `titles` 对象中新增 `document_rewrite: '📄 文档改写'`。验证：侧边栏出现菜单项且标题切换正确
- [ ] 5.2 在 `dashboard.html` 的侧边栏 nav 列表中添加 `<div class="nav-item" data-page="document_rewrite">📄 文档改写</div>`，并在页面容器中添加 `<div class="page" id="page-document_rewrite">` 加载 `document_rewrite.html` 内容。验证：点击侧边栏切换到文档改写页面

## 6. 端到端验证

- [ ] 6.1 完整流程测试：启动应用 → 侧边栏点击"文档改写" → 上传 .docx → 解析预览确认 → 选择风格字数 → 点击改写 → SSE 日志滚动 → 文章填入编辑器 → 预览正常。验证：全流程无报错
- [ ] 6.2 边界测试：上传不支持格式 → 显示错误；上传超大文件 → 显示错误；解析空内容后点改写 → 提示为空。验证：各边界场景正确拦截

```

## docs/openspec/changes/document-rewrite/.openspec.yaml

- Source: docs/openspec/changes/document-rewrite/.openspec.yaml
- Lines: 1-2
- SHA256: dadfffd827282f22738d1215a8fa326bc6e3bda0a2aae3e3af6d203a1ef4c4aa

```md
schema: spec-driven
created: 2026-09-30

```

## docs/openspec/changes/document-rewrite/specs/document-parsing/spec.md

- Source: docs/openspec/changes/document-rewrite/specs/document-parsing/spec.md
- Lines: 1-41
- SHA256: 818b9dfbd35679d5da93a0132db25665fea9e00c5fc27b79f9b85037f3270324

```md
## Purpose

文档内容的解析与提取，负责将不同格式的文档转换为统一的纯文本。

## ADDED Requirements

### Requirement: Word 文档解析
系统 SHALL 使用 python-docx 库提取 .docx 文件中的所有段落文本。

#### Scenario: 标准 Word 文档
- **WHEN** 接收到一个有效的 .docx 文件
- **THEN** 系统遍历所有段落，以 `\n` 连接返回纯文本

### Requirement: PDF 文档解析
系统 SHALL 使用 pdfplumber 库提取 .pdf 文件中的所有页面文本。

#### Scenario: 标准 PDF 文档
- **WHEN** 接收到一个有效的 .pdf 文件
- **THEN** 系统遍历所有页面，提取文本并以 `\n\n` 分隔页面

### Requirement: Markdown/纯文本解析
系统 SHALL 直接读取 .md 和 .txt 文件内容原文返回。

#### Scenario: Markdown 文件
- **WHEN** 接收到一个 .md 文件
- **THEN** 系统以 UTF-8 编码读取并返回原文

#### Scenario: 纯文本文件
- **WHEN** 接收到一个 .txt 文件
- **THEN** 系统以 UTF-8 编码读取并返回原文

### Requirement: 错误处理
系统 SHALL 在解析失败时返回明确的错误信息。

#### Scenario: 文件损坏
- **WHEN** 文件格式正确但内容损坏
- **THEN** 系统捕获异常并返回"文档解析失败"错误

#### Scenario: 编码错误
- **WHEN** .txt 文件使用非 UTF-8 编码
- **THEN** 系统尝试以 UTF-8 读取，失败时以 latin-1 降级读取

```

## docs/openspec/changes/document-rewrite/specs/document-rewrite-workflow/spec.md

- Source: docs/openspec/changes/document-rewrite/specs/document-rewrite-workflow/spec.md
- Lines: 1-38
- SHA256: ff77fae36ceb9b0a155f9e05950fc8c25f11fb67303e4b424b955017e1f1b1bf

```md
## Purpose

将文档解析后的纯文本内容通过 AI 改写模块重新生成适合公众号发布的文章，复用现有改写能力与 SSE 日志流。

## ADDED Requirements

### Requirement: AI 改写调用
系统 SHALL 将用户确认后的文本内容传递给现有 AI 改写模块（`modules/article_rewriter.py`），生成完整的公众号文章。

#### Scenario: 调用改写模块成功
- **WHEN** 用户提交非空的文档内容、风格和字数配置
- **THEN** 系统调用 `rewrite_article()` 并返回 Markdown 格式文章

#### Scenario: LLM 不可用时降级
- **WHEN** AI 模型未配置或调用失败
- **THEN** 系统返回错误信息"AI 模型未配置，请先在系统配置中添加模型"，不生成空文章

### Requirement: SSE 流式日志
系统 SHALL 在改写过程中通过 SSE 实时推送进度日志，完成后将结果填入文章编辑器。

#### Scenario: 实时进度显示
- **WHEN** 用户点击"开始改写"
- **THEN** 页面显示日志卡片，实时滚动显示改写进度消息

#### Scenario: 完成后自动填充
- **WHEN** AI 改写完成
- **THEN** 系统将生成的 Markdown 填入文章编辑器，启用预览和发布按钮

### Requirement: 文章预览与发布
改写完成后，系统 SHALL 支持预览和推送到公众号草稿箱，与现有写稿流程一致。

#### Scenario: 预览生成文章
- **WHEN** 改写完成且文章填入编辑器
- **THEN" 系统渲染 Markdown 预览，用户可查看排版效果

#### Scenario: 推送到草稿箱
- **WHEN** 用户在预览后点击"推送到草稿箱"
- **THEN" 系统调用发布接口将文章推送到公众号

```

## docs/openspec/changes/document-rewrite/specs/document-upload/spec.md

- Source: docs/openspec/changes/document-rewrite/specs/document-upload/spec.md
- Lines: 1-76
- SHA256: 5c89fa2d2cf2cf7bafcba6fba6e7c0f6ccaea150443c5a3a8438e4f40e3596c1

```md
## Purpose

允许用户上传 Word/PDF/Markdown/纯文本格式的文档，系统自动解析文档内容为纯文本，用户确认后调用 AI 改写模块生成适合公众号发布的文章。

## ADDED Requirements

### Requirement: 文件上传与格式校验
系统 SHALL 接受用户上传的文档文件，支持 .docx、.pdf、.md、.txt 四种格式，文件大小不超过 10MB。

#### Scenario: 上传支持的文档格式
- **WHEN** 用户选择一个 .docx 或 .pdf 或 .md 或 .txt 文件上传
- **THEN** 系统接受文件并显示文件名和大小

#### Scenario: 上传不支持的文件格式
- **WHEN** 用户选择一个非支持格式的文件（如 .xlsx、.jpg）
- **THEN** 系统拒绝上传并提示"不支持的文件格式，请使用 .docx/.pdf/.md/.txt"

#### Scenario: 上传超过大小限制的文件
- **WHEN** 用户选择一个超过 10MB 的文件
- **THEN** 系统拒绝上传并提示"文件大小不能超过 10MB"

### Requirement: 文档内容解析
系统 SHALL 将上传的文档解析为纯文本内容，保留段落结构，不含图片和表格。

#### Scenario: 解析 Word 文档
- **WHEN** 用户上传 .docx 文件并确认解析
- **THEN** 系统提取文档所有段落文本，以换行符分隔返回

#### Scenario: 解析 PDF 文档
- **WHEN** 用户上传 .pdf 文件并确认解析
- **THEN** 系统提取 PDF 所有页面的文本内容，以换行符分隔返回

#### Scenario: 解析 Markdown/纯文本
- **WHEN** 用户上传 .md 或 .txt 文件并确认解析
- **THEN** 系统直接读取文件内容原文返回

#### Scenario: 解析失败
- **WHEN** 文件格式正确但内容损坏或无法读取
- **THEN** 系统返回错误信息"文档解析失败，请检查文件是否损坏"

### Requirement: 解析预览与编辑
系统 SHALL 在生成文章前展示解析结果，允许用户在文本框中编辑修改。

#### Scenario: 显示解析结果
- **WHEN** 文档解析成功
- **THEN** 系统将解析文本填充到可编辑文本框，用户可以预览和修改

#### Scenario: 空内容拦截
- **WHEN** 解析结果为空或用户将编辑框清空后点击"开始改写"
- **THEN** 系统提示"内容为空，请先上传文档或输入文字"

### Requirement: 改写配置与生成
系统 SHALL 允许用户选择文章风格和目标字数，然后调用 AI 改写模块生成文章。

#### Scenario: 使用默认配置生成
- **WHEN** 用户在解析预览页直接点击"开始改写"（未修改风格和字数）
- **THEN** 系统使用默认风格"观点评论"和默认字数 2000 字生成文章

#### Scenario: 自定义配置生成
- **WHEN** 用户选择了其他风格（如"深度科普"）和字数（如 3000）后点击"开始改写"
- **THEN** 系统使用用户选择的参数调用 AI 改写

#### Scenario: 改写过程流式反馈
- **WHEN** 用户点击"开始改写"
- **THEN** 系统通过 SSE 实时推送改写进度日志，完成后将结果填入文章编辑器

### Requirement: 前端页面与导航
系统 SHALL 新增独立页面和侧边栏入口，与现有页面风格保持一致。

#### Scenario: 侧边栏导航
- **WHEN** 用户在侧边栏点击"📄 文档改写"
- **THEN** 系统切换到文档改写页面，显示上传区

#### Scenario: 页面样式一致
- **WHEN** 用户打开文档改写页面
- **THEN** 页面使用与 cover_maker.html、hotrank.html 相同的 CSS 风格

```
