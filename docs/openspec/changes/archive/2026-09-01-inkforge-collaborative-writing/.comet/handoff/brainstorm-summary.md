# Brainstorm Summary

- Change: inkforge-collaborative-writing
- Date: 2026-08-31

## 确认的技术方案

### 整体架构
- 在现有 Flask 应用内新增 `/collaborative` 蓝图，复用认证/账号/数据库
- 后端 4 个新增/拆分模块：`ai_writer.py`（拆分 3 函数）、`version_manager.py`、`article_history.py`、`ai_labeler.py`
- 数据库新增 4 张表：`collaborative_projects`、`article_history`、`version_snapshots`、`ai_label_config`
- 前端原生 JavaScript，工作台为单页多阶段应用

### AI 交互方式
- 采用方案 A：同步 POST 请求 + 前端加载状态
- Flask 请求超时 120s
- AI 生成接口为 POST，数据保存接口为 PUT（幂等）

### 数据模型
- 选题/大纲/内容用 JSON 字符串存储（灵活应对结构变化）
- `article_history.ai_label` 保存标识文案快照（管理员修改不影响已保存文章）
- `version_snapshots.content_json` 保存完整项目状态

### API 设计
- 13 个 REST API 端点（`/api/collaborative/*`）
- `generate-content` 的 `section_id` 可选：有则生成单段，无则生成全部
- 保存到历史文章时后端强制附加 AI 标识并校验

### 前端结构
- 单页多阶段工作台（非多页面路由）
- 阶段导航显示进度，已完成阶段可点击回看
- 版本历史侧边栏可折叠

### 平台功能移除
- 完全移除 `wx_publisher.py`、`md_converter.py`、`cover_generator.py`、`cover_maker.py`
- 移除 `web_app.py` 中平台相关路由和菜单
- 移除平台相关配置文件（`domains_config.json` 等）

## 关键取舍与风险

- 同步 vs 流式：选同步（实现快，MVP 优先）
- 版本快照保留策略：自动保留 20 个，手动标记无限制
- 超时策略：120s 平衡点
- 主要风险：LLM 超时、大纲结构不一致、版本膨胀、AI 标识绕过

## 测试策略

- 单元测试：pytest，LLM 调用 mock
- 集成测试：Flask test client，端到端流程
- 手动测试：浏览器操作前端交互

## Spec Patch

无（现有 specs 无需回写）
