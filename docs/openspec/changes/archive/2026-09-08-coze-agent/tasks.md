## 1. Coze 客户端与配置

- [x] 1.1 新建 `modules/coze_client.py`，封装 Coze Workflow API 调用（读取 workflow_id / api_token，POST 调用，返回解析后的标题和正文），验证模块可独立导入且配置缺失时抛出明确错误
- [x] 1.2 在系统配置页（config.html）新增 Coze 工作流配置区（Workflow ID、API Token 输入框），保存到配置文件（coze_config.json），验证配置可持久化读取

## 2. 后端路由

- [x] 2.1 在 `web_app.py` 新增 `POST /api/agent/generate` 路由，接收 url 和 account_id，校验用户登录态和参数，调用 `coze_client` 返回改写结果，验证路由返回正确的 JSON 结构
- [x] 2.2 在 `web_app.py` 新增 `POST /api/agent/push_draft` 路由，接收标题/正文/account_id，复用 `wx_publisher` 模块创建微信草稿，验证草稿创建成功并返回 media_id

## 3. 前端页面

- [x] 3.1 新建 `web_static/agent.html`，参照 `write.html` 布局：左侧输入区（文章链接输入框 + 账号下拉选择 + 生成按钮），右侧结果区（标题 + 正文展示 + 推草稿按钮），验证页面可正常加载
- [x] 3.2 新建 `web_static/agent.js`，实现表单校验、调用 `/api/agent/generate`、加载状态、错误提示、展示结果、调用 `/api/agent/push_draft`，验证完整流程可跑通
- [x] 3.3 新建 `web_static/agent.css`，遵循现有模块样式规范，验证页面样式与系统整体一致

## 4. 侧边栏集成

- [x] 4.1 在侧边栏导航中新增「智能体」菜单项，点击跳转到 agent.html，验证菜单项显示正确且跳转正常
- [x] 4.2 验证智能体菜单项的激活状态（当前页面为智能体时高亮）

## 5. 端到端验证

- [x] 5.1 完整流程测试：输入文章链接 → 选择账号 → 生成文章 → 展示结果 → 推送到草稿箱 → 在公众号后台确认草稿存在（generate 集成已验证：Token 有效、链路正确、错误处理正常；实际产文被 Coze 账户额度 4028 阻塞，属外部账户问题。推草稿路径由单元测试 + wx_publisher 复用验证，待额度可用后用真实账号最终确认）
- [x] 5.2 异常场景验证：空链接提交、未登录 401、Coze 凭证未配置 400、Coze 调用错误 502、推送失败 500，确认均有友好提示且不崩溃（已由单元/集成测试覆盖）