# Comet Design Handoff

- Change: coze-agent
- Phase: design
- Mode: compact
- Context hash: ddd55844c88ba5baf875480587f355f818f1dad33bc98756414f799ccf789dc8

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## docs/openspec/changes/coze-agent/proposal.md

- Source: docs/openspec/changes/coze-agent/proposal.md
- Lines: 1-28
- SHA256: e1d6a61b38d41c130256543acbff188e1538f5440a275f26836a16930d4ad17a

```md
## Why

当前系统的 AI 写稿功能（`ai_writer`）依赖本地配置的 LLM（DeepSeek/OpenAI 等），用户需要自己管理 API Key 和提示词。现在你创建了一个 Coze 工作流，能够自动从文章链接提取原文并改写为原创文章——但系统缺少一个入口来调用这个外部智能体。需要在侧边栏新增「智能体」菜单，集成 Coze 工作流，让用户无需离开系统就能完成"输入链接 → 获取原创稿 → 推草稿"的全流程。

## What Changes

- **新增侧边栏菜单项「智能体」**：在现有侧边栏导航中增加一个独立入口，与「写稿」「一键排版」等模块并列
- **新增智能体页面**：类写稿页布局，左侧输入区（文章链接 + 公众号账号选择），右侧结果展示区（Coze 改写后的文章）
- **新增后端 Coze Workflow API 调用路由**：Flask 新增路由，接收文章链接和账号凭证，调用 Coze Workflow API，返回改写结果
- **支持一键推送到草稿箱**：改写结果可直接调用现有微信发布流程推送到公众号草稿箱

## Capabilities

### New Capabilities

- `agent`: 智能体模块——输入文章链接与公众号账号，调用 Coze 工作流自动提取原文并改写为原创文章，展示结果并支持推送到草稿箱。涵盖侧边栏入口、智能体页面、后端 Coze 调用路由的完整链路。

### Modified Capabilities

（无——现有模块的需求不变，本 change 只新增独立功能）

## Impact

- **前端**：`web_static/` 新增 `agent.html` + `agent.js` + `agent.css`；修改侧边栏导航文件（`common.js` 或公共 HTML）增加菜单项
- **后端**：`web_app.py` 新增 Coze Workflow API 调用路由（`/api/agent/*`）；可能新增 `modules/coze_client.py` 封装 Coze API
- **依赖**：无新增 Python 依赖（Coze 调用使用现有 `requests`）
- **配置**：Coze Workflow ID、API Token 的配置方式（环境变量或系统配置页）
- **不受影响**：现有 `ai_writer`、`auto_selector`、写稿页、排版页等模块保持不变

```

## docs/openspec/changes/coze-agent/design.md

- Source: docs/openspec/changes/coze-agent/design.md
- Lines: 1-72
- SHA256: e047422c228ca06c9635ddb150a60eb1b4921046186bc9afbe58910e1983c869

```md
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

```

## docs/openspec/changes/coze-agent/tasks.md

- Source: docs/openspec/changes/coze-agent/tasks.md
- Lines: 1-25
- SHA256: 42c3011af09da191cefdd04263c70aac2450068d3f0e9d7a5b01d53710739df7

```md
## 1. Coze 客户端与配置

- [ ] 1.1 新建 `modules/coze_client.py`，封装 Coze Workflow API 调用（读取 workflow_id / api_token，POST 调用，返回解析后的标题和正文），验证模块可独立导入且配置缺失时抛出明确错误
- [ ] 1.2 在系统配置页（config.html / config.js）新增 Coze 工作流配置区（Workflow ID、API Token 输入框），保存到数据库或配置文件，验证配置可持久化读取

## 2. 后端路由

- [ ] 2.1 在 `web_app.py` 新增 `POST /api/agent/generate` 路由，接收 article_url 和 account_id，校验用户登录态和参数，调用 `coze_client` 返回改写结果，验证路由返回正确的 JSON 结构
- [ ] 2.2 在 `web_app.py` 新增 `POST /api/agent/push_draft` 路由，接收标题/正文/account_id，复用 `wx_publisher` 模块创建微信草稿，验证草稿创建成功并返回 media_id

## 3. 前端页面

- [ ] 3.1 新建 `web_static/agent.html`，参照 `write.html` 布局：左侧输入区（文章链接输入框 + 账号下拉选择 + 生成按钮），右侧结果区（标题 + 正文展示 + 推草稿按钮），验证页面可正常加载
- [ ] 3.2 新建 `web_static/agent.js`，实现表单校验、调用 `/api/agent/generate`、加载状态、错误提示、展示结果、调用 `/api/agent/push_draft`，验证完整流程可跑通
- [ ] 3.3 新建 `web_static/agent.css`，遵循现有模块样式规范，验证页面样式与系统整体一致

## 4. 侧边栏集成

- [ ] 4.1 在侧边栏导航中新增「智能体」菜单项（修改 common.js 或公共 HTML 模板），点击跳转到 agent.html，验证菜单项显示正确且跳转正常
- [ ] 4.2 验证智能体菜单项的激活状态（当前页面为智能体时高亮）

## 5. 端到端验证

- [ ] 5.1 完整流程测试：输入文章链接 → 选择账号 → 生成文章 → 展示结果 → 推送到草稿箱 → 在公众号后台确认草稿存在
- [ ] 5.2 异常场景验证：空链接提交、Coze API 超时/错误、推送失败，确认均有友好提示且不崩溃

```

## docs/openspec/changes/coze-agent/specs/agent/spec.md

- Source: docs/openspec/changes/coze-agent/specs/agent/spec.md
- Lines: 1-67
- SHA256: 9f3ae8de016904f90175b40cc866376ed427973b600ac10e9ecfeba4c7182aaf

```md
## Purpose

智能体模块允许用户输入一篇公众号文章链接并选择目标公众号账号，系统调用 Coze 工作流自动提取原文并改写为原创文章，在页面展示结果并支持一键推送到公众号草稿箱。

## ADDED Requirements

### Requirement: 侧边栏显示智能体菜单项
系统 SHALL 在侧边栏导航中显示一个名为「智能体」的菜单项，与「写稿」「一键排版」等现有模块并列。

#### Scenario: 已登录用户查看侧边栏
- **WHEN** 已登录用户打开任意页面
- **THEN** 侧边栏显示「智能体」菜单项，点击后跳转到智能体页面

#### Scenario: 智能体菜单项激活状态
- **WHEN** 用户点击「智能体」菜单项
- **THEN** 该菜单项显示为激活（高亮）状态，页面内容区切换为智能体页面

### Requirement: 智能体页面输入表单
智能体页面 SHALL 展示一个输入表单，包含文章链接输入框和公众号账号下拉选择器。

#### Scenario: 页面加载时加载账号列表
- **WHEN** 用户打开智能体页面
- **THEN** 账号下拉选择器加载当前用户配置的所有公众号账号

#### Scenario: 表单校验
- **WHEN** 用户未填写文章链接或未选择账号就点击「生成文章」
- **THEN** 系统提示用户填写必填项，不发起 Coze 调用

### Requirement: 调用 Coze 工作流改写文章
系统 SHALL 将文章链接和所选账号的 AppID/AppSecret 发送到 Coze Workflow API，并展示改写后的文章。

#### Scenario: 成功调用 Coze 工作流
- **WHEN** 用户填写了有效文章链接并选择账号后点击「生成文章」
- **THEN** 系统调用 Coze Workflow API，等待返回后将改写后的文章标题和正文展示在结果区

#### Scenario: Coze 工作流调用失败
- **WHEN** Coze Workflow API 返回错误或超时
- **THEN** 系统在页面上显示友好的错误提示（如"生成失败，请稍后重试"），不丢失用户已填写的输入

#### Scenario: 调用过程中显示加载状态
- **WHEN** 系统正在调用 Coze Workflow API
- **THEN** 页面显示加载指示器，禁用「生成文章」按钮防止重复提交

### Requirement: 展示改写结果
系统 SHALL 在结果区展示 Coze 返回的文章标题和正文内容。

#### Scenario: 展示文章标题和正文
- **WHEN** Coze 工作流返回改写结果
- **THEN** 结果区显示文章标题和正文，内容可滚动查看

### Requirement: 推送文章到草稿箱
系统 SHALL 允许用户将改写后的文章一键推送到公众号草稿箱。

#### Scenario: 成功推送到草稿箱
- **WHEN** 用户在改写结果展示后点击「推送到草稿箱」
- **THEN** 系统使用所选账号的凭证，通过现有微信发布流程将文章创建为草稿，并提示成功

#### Scenario: 推送失败
- **WHEN** 推送到草稿箱时微信 API 返回错误
- **THEN** 系统显示错误原因（如 access_token 获取失败），文章内容保留在页面中

### Requirement: Coze 凭证配置
系统 SHALL 支持配置 Coze Workflow API 所需的 Workflow ID 和 API Token。

#### Scenario: 凭证未配置时提示
- **WHEN** 用户未配置 Coze 凭证就尝试生成文章
- **THEN** 系统提示用户先在系统配置中完成 Coze 工作流配置

```
