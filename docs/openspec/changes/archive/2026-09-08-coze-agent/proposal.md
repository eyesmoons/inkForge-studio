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
