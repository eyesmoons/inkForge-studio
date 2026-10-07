# Brainstorm Summary

- Change: coze-agent
- Date: 2026-09-08

## 确认的技术方案

### 架构
- Flask 后端 + 原生 HTML/JS 多页面前端，遵循现有模块组织模式
- 新增 `modules/coze_client.py` 封装 Coze SDK 调用（隔离外部依赖）
- 新增 `web_static/agent.html` + `agent.css`（页面逻辑内联 `<script>`，遵循现有约定）
- 修改 `web_app.py` 新增 `/api/agent/generate` 和 `/api/agent/push_draft` 路由
- 修改 `config.html` + `common.js` 新增 Coze 工作流配置管理
- 修改现有 8 个 HTML 页面的侧边栏，新增「智能体」菜单项

### Coze 集成
- **SDK**：`cozepy`（Coze 官方 Python SDK），`pip install cozepy`
- **认证**：`TokenAuth(token=...)` + `COZE_CN_BASE_URL`（api.coze.cn）
- **Workflow ID**：`7569130427475705882`
- **调用方式**：非流式 `coze.workflows.runs.run()`，60s 超时
- **输入参数**：`url`, `app_id`, `app_secret`, `prompt`（4 个，key 必须与 Coze 工作流定义一致）
- **输出**：title + content 两个字段（精确 key 名待实现时从 Coze 实际返回确认）

### 前端表单
- 文章链接输入框（`url`）
- 公众号账号下拉选择器（复用 `loadAccounts()`，默认选中系统默认账号）
- 提示词输入框（`prompt`，用户可编辑，默认值"不要抄袭,去除AI味"）
- 「生成文章」按钮 → 调用 `/api/agent/generate`
- 结果区：标题 + 正文展示 + 「推送到草稿箱」按钮

### 推送草稿
- `POST /api/agent/push_draft` 接收 title + content + account_id
- 复用现有 `wx_publisher.WeChatPublisher` 创建微信草稿

### Coze 配置管理
- config.html 新增「Coze 工作流配置」手风琴区（Workflow ID、API Token）
- 后端新增 `/api/coze_config` GET/PUT 路由，存 DB

### 安全
- AppSecret 不暴露到前端，只传 account_id，后端从 DB 读取

## 关键取舍与风险

- **侧边栏逐页复制**：现有模式代价，保持一致性，未来可重构为共享组件
- **非流式调用**：简单可靠，60s 超时 + 前端加载动画
- **cozepy 新依赖**：加入 requirements.txt
- **Coze 执行等待**：前端禁用按钮防重复提交

## 测试策略

- 单元：`coze_client.py` mock 测试
- 集成：路由参数校验和错误处理
- 端到端：输入链接 → 生成 → 展示 → 推草稿 → 确认草稿箱
- 异常：空链接、Coze 超时/错误、凭证未配置、推送失败

## Spec Patch

无——现有 delta spec 的验收场景已覆盖设计方案，无需回写。
