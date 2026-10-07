## Context

系统现有架构为 Flask 后端 + 原生 HTML/JS 多页面前端，各功能模块（写稿、排版、选题等）以独立 HTML 页面 + 对应 JS 文件组织。公众号账号和 AI 配置存储在 SQLite 数据库（`accounts` 表）中。现有 `ai_writer` 模块通过 OpenAI 兼容接口调用 LLM 写稿，`wx_publisher` 模块负责微信草稿/发布流程。本 change 新增独立的「智能体」模块，通过 Coze Workflow API 提供文章改写能力，不修改现有模块。

## Goals / Non-Goals

**Goals:**
- 新增侧边栏「智能体」入口和独立页面
- 通过 Coze Workflow API 实现"输入链接 → 改写为原创文章"
- 改写结果可一键推送到公众号草稿箱
- 复用现有账号体系（AppID/AppSecret）和微信发布流程

**Non-Goals:**
- 不替换或修改现有 `ai_writer` 模块
- 不实现多轮对话或流式输出
- 不在系统内实现 Coze 工作流内部逻辑
- 不新增数据库表（复用 `accounts` 表获取账号凭证）

## Decisions

### 决策 1：Coze 调用方式——后端同步调用 Workflow API

**选择**：Flask 后端路由调用 Coze Workflow API（`POST /v1/workflows/run`），同步等待结果后返回前端。

**备选方案**：
- A. 前端直接调用 Coze API → 暴露 AppSecret 到浏览器，不安全，排除
- B. 后端异步任务 + 前端轮询 → 增加复杂度，当前 Coze 工作流执行时间预计 <30s，同步可接受

**理由**：用户输入含 AppSecret，必须走后端；同步调用最简单，符合"类写稿页"交互预期。若未来 Coze 响应慢再升级为异步。

### 决策 2：Coze 凭证存储位置

**选择**：Coze Workflow ID 和 API Token 存储在系统配置中（通过「系统配置」页面管理），与现有 AI 模型配置并列。

**备选方案**：
- A. 环境变量（`COZE_WORKFLOW_ID` / `COZE_API_TOKEN`）→ 部署友好但用户已习惯在 Web 界面配置
- B. `config.json` 文件 → 与 AI 配置分散，不一致

**理由**：保持与现有 AI 模型管理一致的用户体验，降低学习成本。

### 决策 3：账号凭证来源

**选择**：从 `accounts` 表读取用户已配置的公众号账号，以下拉选择器展示，用户选择后自动填充 AppID/AppSecret。

**理由**：复用现有账号体系，用户无需重复输入凭证，与写稿/排版模块行为一致。

### 决策 4：前端页面组织

**选择**：新增 `agent.html` + `agent.js` + `agent.css`，遵循现有模块的文件组织约定（如 `write.html` / `rewrite.html`）。

**理由**：保持与现有代码风格一致，每个模块自包含。

### 决策 5：后端路由设计

**选择**：在 `web_app.py` 新增 `/api/agent/` 前缀的路由：
- `POST /api/agent/generate` — 调用 Coze 工作流，返回改写结果
- `POST /api/agent/push_draft` — 调用现有微信发布流程创建草稿

**理由**：RESTful 风格，与现有 `/api/` 路由约定一致。推送草稿复用 `wx_publisher` 模块。

## Risks / Trade-offs

- **Coze API 超时风险** → 设置合理超时（如 60s），超时后提示用户重试；若频繁超时再考虑异步改造
- **Coze 工作流输入格式变更** → 封装 `coze_client.py` 隔离变化，Coze 接口变动只需修改该文件
- **AppSecret 传输安全** → 后端路由通过 session 验证用户身份，AppSecret 只在服务端内存中处理，不暴露到前端
- **改写质量依赖 Coze 工作流** → 系统只负责传递参数和展示结果，内容质量由用户在 Coze 平台控制

## Open Questions

- Coze Workflow API 的具体 endpoint 格式和认证方式（Bearer <REDACTED> / API Key Header）——需要用户提供 Coze 工作流文档或链接
- Coze 工作流定义的输入参数名称（article_url / app_id / app_secret 的具体字段名）——需要确认
- Coze 工作流返回结果的 JSON 结构（标题和正文的字段路径）——需要确认
