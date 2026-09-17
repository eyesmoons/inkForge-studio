## Why

inkForge-studio 当前是一个带有特定平台垂直功能（草稿推送、平台排版、封面生成）的 AI 辅助写作工具。本次变革要做一次彻底的产品定位转型：(1) 去掉所有平台专属功能（草稿推送、平台排版、封面生成、平台绑定菜单），抽象为通用 AI 辅助写作平台；(2) 解决创作者恐惧 AI 替代自己的心理阻力；(3) 无 AI 标识的内容违反《人工智能生成合成内容标识办法》合规要求。变革后产品是"人机协同创作工具"——创作者输入想法，AI 辅助生成选题、大纲、内容，创作者全程主导决策，最终保存到历史文章。

## What Changes

- **新增协同创作工作台**：在现有 Flask Web 应用内新增"协同创作"页面/路由，共用现有登录、账号、数据库体系
- **AI 辅助创作三拍子**：生成选题 → 生成大纲 → 生成内容（逐段或全部），每步都是"AI 提议、创作者决策、下一步"
- **新增历史文章管理**：创作完成保存到历史文章列表，支持查看、继续编辑、版本回溯
- **新增版本管理**：记录人机协同写作过程，支持历史回溯与对比
- **新增强制 AI 标识**：保存文章时自动附加显式 AI 生成声明，创作者不可删除或关闭
- **移除平台专属功能**：移除草稿推送、平台排版（MD 转平台 HTML）、封面生成、平台相关菜单和配置（**BREAKING**：现有平台垂直功能被移除）
- **通用化改造**：产品不再与任何平台绑定，是独立的 AI 辅助写作平台

## Capabilities

### New Capabilities
- `collaborative-workbench`: 人机协同创作工作台整体能力，包含创作流程编排、AI 交互界面、状态管理
- `ai-topic-generation`: AI 根据创作者输入的想法生成多个选题建议，支持创作者选择或修改
- `ai-outline-generation`: AI 根据选题生成结构化大纲，支持创作者编辑、增删、重排节点
- `ai-content-generation`: AI 基于大纲逐段或全部生成内容，支持逐段采纳/修改/重写
- `article-history`: 历史文章管理，支持保存、查看、继续编辑、版本回溯
- `version-management`: 写作过程版本快照、历史回溯、版本对比
- `ai-content-labeling`: 强制 AI 生成内容标识（显式声明），合规不可关闭

### Modified Capabilities
- 无（现有 `openspec/specs/` 目录为空，无已有 capability 需要修改）

## Impact

- **代码**：`web_app.py` 新增协同创作路由与页面，移除平台相关路由和菜单；`modules/ai_writer.py` 拆分为选题/大纲/内容三个辅助模式；新增 `modules/version_manager.py`、`modules/ai_labeler.py`、`modules/article_history.py`；移除 `modules/wx_publisher.py`、`modules/md_converter.py`、`modules/cover_generator.py`、`modules/cover_maker.py`
- **数据库**：新增版本历史表、AI 标识配置表、历史文章表；移除平台相关表字段
- **API**：新增协同创作 REST API 端点（`/api/collaborative/*`）；移除平台相关 API
- **依赖**：无新增外部依赖，复用现有 Flask + requests + 数据库栈
- **用户影响**：平台垂直功能被移除，用户需使用新的协同创作流程；现有平台相关配置不再可用
