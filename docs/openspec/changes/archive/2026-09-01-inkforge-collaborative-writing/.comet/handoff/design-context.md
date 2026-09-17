# Comet Design Handoff

- Change: inkforge-collaborative-writing
- Phase: design
- Mode: compact
- Context hash: 398074ab960bf9833f133d78576be793eefc68829cdaa05efd81ab43f6a555fe

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## docs/openspec/changes/inkforge-collaborative-writing/proposal.md

- Source: docs/openspec/changes/inkforge-collaborative-writing/proposal.md
- Lines: 1-35
- SHA256: b6c9de0064e95225f71a84c0f66498c2f1a0c2ac7cf0129740315539d5da5747

```md
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

```

## docs/openspec/changes/inkforge-collaborative-writing/design.md

- Source: docs/openspec/changes/inkforge-collaborative-writing/design.md
- Lines: 1-97
- SHA256: 667d1ef9a56f79458f80c70bb27458d1997d69ab64ac954d2d3603460d1d00b8

[TRUNCATED]

```md
## Context

inkForge-studio 当前是一个AI 辅助写作工具（Flask Web 应用 + Python 模块）。主要模块包括 `web_app.py`（Flask 后端）、`modules/ai_writer.py`（AI 写作）、`modules/auto_selector.py`（选题建议）、`（MD 转平台 HTML）、`modules/cover_generator.py`（封面生成）、`modules/material_library.py`（素材库）。

本次变革要做一次彻底的产品定位转型：去掉所有平台垂直功能，重构为通用 AI 辅助写作平台。新工作台流程为"想法 → 选题 → 大纲 → 内容 → 保存到历史文章"。详见 proposal.md 的 Why 章节。

## Goals / Non-Goals

**Goals:**
- 在现有 Flask 应用内新增协同创作路由与页面，复用现有用户认证、账号管理、数据库
- 将 AI 写作拆分为"选题生成 / 大纲生成 / 内容生成"三个辅助模式，每步由创作者主动触发并决策
- 实现历史文章管理，创作完成可保存、查看、继续编辑
- 实现版本快照机制，记录人机协同过程
- 强制 AI 标识，满足合规要求
- 移除所有平台专属功能（草稿推送、平台排版、封面生成、平台菜单）

**Non-Goals:**
- 不新增外部依赖（复用现有 Flask + requests + SQLite 栈）
- 不做多平台分发（聚焦写作协作本身）
- 不做移动端原生应用
- 不做多人实时协同编辑
- 不保留平台草稿推送能力（完全移除）

## Decisions

### 决策 1：协同创作在现有 Flask 应用内的集成方式

**选择**：在 `web_app.py` 中新增 `/collaborative/*` 路由蓝图，新增 `templates/collaborative/*` 页面模板，前端采用原生 JavaScript（与现有页面风格一致）。

**替代方案**：
- A. 独立 Flask 应用（单独端口）→ 需要独立部署、独立会话管理，增加运维复杂度
- B. 前后端分离（React/Vue 前端）→ 引入新框架，与现有技术栈不一致

**理由**：复用现有认证、账号、数据库体系，保持技术栈一致，降低部署复杂度。

### 决策 2：AI 辅助模式拆分

**选择**：将现有 `modules/ai_writer.py` 拆分为三个辅助函数：`generate_topics()`、`generate_outline()`、`generate_content()`，共享 LLM 配置检测逻辑。

**替代方案**：
- A. 保持单一 `ai_writer.py`，通过参数区分模式 → 函数职责不清，难以独立演进
- B. 三个独立模块文件 → 过度拆分，共享逻辑重复

**理由**：函数级拆分保持模块内聚，同时让三种辅助能力可独立调用和测试。

### 决策 3：版本管理存储方式

**选择**：在 SQLite 数据库中新增 `version_snapshots` 表，存储版本元数据 + 内容 JSON（选题、大纲、内容状态）。

**替代方案**：
- A. 文件系统存储（每版本一个 JSON 文件）→ 难以查询和关联用户/项目
- B. 专用版本管理库（如 dulwich/gitpython）→ 引入新依赖，对非技术创作者不透明

**理由**：复用现有 SQLite 数据库，版本数据与用户/项目天然关联，查询和备份简单。

### 决策 4：AI 标识实现方式

**选择**：在保存文章流程中通过 `ai_labeler.py` 模块强制附加标识，标识文案存储在系统配置表（管理员可配置），保存时校验标识存在。

**替代方案**：
- A. 前端模板硬编码标识 → 创作者可通过修改模板绕过
- B. 数据库触发器自动附加 → 与业务逻辑耦合，难以维护

**理由**：后端模块强制校验，前端无法绕过；配置表支持管理员调整文案。

### 决策 5：平台专属功能移除策略

**选择**：完全移除 `modules/wx_publisher.py`（草稿推送）、`modules/md_converter.py`（MD 转平台 HTML）、`modules/cover_generator.py` 和 `modules/cover_maker.py`（封面生成），移除 `web_app.py` 中平台相关路由和菜单，移除平台相关配置文件（`domains_config.json` 等）。

**替代方案**：
- A. 保留平台功能但隐藏 → 代码负担重，与"通用平台"定位矛盾
- B. 抽象为通用发布能力 → 用户明确不做多平台分发，无需抽象层

**理由**：用户明确要求去掉平台相关所有菜单、代码和内容，产品定位是独立通用写作平台。

## Risks / Trade-offs

- **[风险] 现有平台用户流失** → 原有平台草稿推送能力被移除。**缓解**：明确告知用户转型方向，历史文章仍保留查看能力。
- **[风险] 创作者学习成本** → 从原有工作流切换到新协同创作流程需要适应。**缓解**：提供引导式教程和示例项目。
- **[风险] AI 标识影响阅读体验** → 创作者可能担心标识降低内容可信度。**缓解**：标识文案强调"辅助"而非"替代"，合规同时减少心理阻力。

```

Full source: docs/openspec/changes/inkforge-collaborative-writing/design.md

## docs/openspec/changes/inkforge-collaborative-writing/tasks.md

- Source: docs/openspec/changes/inkforge-collaborative-writing/tasks.md
- Lines: 1-82
- SHA256: cde02f8310f80ffad7312d244ca8a10e017ab5596053f926cdbc88fca5b938d1

[TRUNCATED]

```md
## 1. 数据库与基础设施

- [ ] 1.1 在 `user_db.py` 中新增 `version_snapshots` 表（字段：id, project_id, user_id, version_name, content_json, created_at, trigger_type）和 `ai_label_config` 表（字段：id, label_text, updated_at, updated_by），验证：表创建成功且可通过 SQL 查询
- [ ] 1.2 在 `user_db.py` 中新增 `collaborative_projects` 表（字段：id, user_id, title, current_phase, topic_json, outline_json, content_json, created_at, updated_at）和 `article_history` 表（字段：id, user_id, title, topic_json, outline_json, content_json, ai_label, created_at, updated_at），验证：表创建成功且与 users 表外键关联正确
- [ ] 1.3 新增 `modules/version_manager.py` 模块，实现 `create_snapshot()`、`list_versions()`、`get_version()`、`compare_versions()`、`rollback_to_version()` 函数，验证：单元测试覆盖各函数

## 2. AI 辅助能力拆分

- [ ] 2.1 在 `modules/ai_writer.py` 中新增 `generate_topics(idea, count=5)` 函数，接收想法返回多个选题建议（每个包含标题和说明），验证：调用返回包含 3-5 个选题的列表
- [ ] 2.2 在 `modules/ai_writer.py` 中新增 `generate_outline(topic, context=None)` 函数，基于选题返回结构化大纲 JSON，验证：调用返回包含章节和要点的 JSON 结构
- [ ] 2.3 在 `modules/ai_writer.py` 中新增 `generate_content(outline, section=None)` 函数，基于大纲生成内容，section 为 None 时生成全部内容，验证：传入大纲返回段落内容，section 参数控制是否仅生成单段
- [ ] 2.4 确保三个新函数共享现有 LLM 配置检测逻辑（`_detect_llm_backend`），验证：在无 API key 时自动降级到 Ollama 或内置模板

## 3. AI 标识模块

- [ ] 3.1 新增 `modules/ai_labeler.py` 模块，实现 `get_label_text()`（从配置表读取，返回默认文案）、`attach_label(content)`（在内容末尾附加标识）、`validate_content(content)`（校验标识存在），验证：单元测试覆盖标识附加和校验逻辑
- [ ] 3.2 实现管理员配置接口 `set_label_text(new_text, admin_user)`，验证：非管理员调用被拒绝，管理员调用成功更新配置

## 4. 历史文章模块

- [ ] 4.1 新增 `modules/article_history.py` 模块，实现 `save_article()`、`list_articles()`、`get_article()`、`update_article()`、`delete_article()` 函数，验证：单元测试覆盖各函数
- [ ] 4.2 在保存文章流程中集成 `ai_labeler.attach_label()` 自动附加 AI 标识，验证：保存的文章末尾包含 AI 标识
- [ ] 4.3 在保存文章流程中集成 `ai_labeler.validate_content()` 校验，标识缺失时阻止保存，验证：标识缺失时保存被阻止并返回明确错误

## 5. 协同创作路由与页面

- [ ] 5.1 在 `web_app.py` 中新增 `/collaborative` 路由蓝图，包含：`GET /`（创作列表）、`POST /create`（新建创作项目）、`GET /<project_id>`（进入创作项目），验证：路由可访问且需要登录
- [ ] 5.2 新增 `templates/collaborative/list.html` 页面，展示当前用户的协同创作项目列表和历史文章列表，验证：页面正确渲染两个列表并按更新时间排序
- [ ] 5.3 新增 `templates/collaborative/workbench.html` 页面，包含创作流程导航（选题/大纲/内容/保存四个阶段指示器），验证：页面展示流程导航且当前阶段高亮
- [ ] 5.4 实现创作状态持久化 API：`GET /api/collaborative/<project_id>/state` 和 `POST /api/collaborative/<project_id>/state`，验证：状态保存后刷新页面可恢复

## 6. 选题生成环节前端

- [ ] 6.1 在工作台页面实现"选题生成"面板：想法输入框 + "生成选题"按钮 + 选题卡片列表，验证：点击按钮后展示 AI 生成的选题卡片
- [ ] 6.2 实现选题卡片展示：标题、说明、"选择此选题"按钮、"修改"按钮，验证：选题卡片正确渲染且可交互
- [ ] 6.3 实现"自定义选题"功能：创作者可跳过 AI 生成直接输入选题，验证：自定义选题后进入大纲生成环节
- [ ] 6.4 实现"确认选题，进入大纲生成"按钮，确认后触发版本快照，验证：确认后选题进入只读状态且版本历史出现新快照

## 7. 大纲生成环节前端

- [ ] 7.1 在工作台页面实现"大纲生成"面板：选题展示 + "生成大纲"按钮 + 大纲树展示区域，验证：点击按钮后展示 AI 生成的大纲结构
- [ ] 7.2 实现大纲编辑功能：节点双击编辑、添加节点、删除节点、拖拽排序，验证：编辑后大纲 JSON 正确更新
- [ ] 7.3 实现"锁定大纲，进入内容生成"按钮，锁定后触发版本快照，验证：锁定后大纲进入只读状态且版本历史出现新快照

## 8. 内容生成环节前端

- [ ] 8.1 在工作台页面实现"内容生成"面板：大纲章节列表 + 每个章节的"生成内容"按钮 + "为全部大纲生成内容"按钮，验证：两种触发方式均可正常工作
- [ ] 8.2 实现段落级内容展示：按大纲章节分组，每个段落显示正文和对应大纲节点标注，验证：段落按大纲结构分组展示
- [ ] 8.3 实现内容二次修改功能：创作者可直接编辑段落文本，修改后自动保存，验证：编辑后内容更新且状态变为"已修改"
- [ ] 8.4 实现内容生成进度指示器（已生成/总章节数），验证：进度随内容生成实时更新
- [ ] 8.5 实现"保存到历史文章"按钮，汇总所有段落为完整文章，验证：点击后进入保存环节

## 9. 版本管理前端

- [ ] 9.1 在工作台侧边栏实现"版本历史"面板：版本列表（时间、名称、变更摘要），验证：版本列表按时间倒序展示
- [ ] 9.2 实现版本内容查看（只读模式），验证：点击历史版本展示该版本完整内容
- [ ] 9.3 实现版本对比功能：选择两个版本查看差异，验证：差异视图正确高亮新增/删除/修改
- [ ] 9.4 实现版本回溯功能：回溯到历史版本创建新版本，验证：回溯后版本历史完整保留且当前内容更新

## 10. 历史文章前端

- [ ] 10.1 实现历史文章列表页面：标题、保存时间、字数、"查看"/"继续编辑"/"删除"操作，验证：列表正确渲染且操作按钮可用
- [ ] 10.2 实现历史文章查看页面：完整内容展示（含 AI 标识），验证：查看页面展示正文和末尾 AI 标识
- [ ] 10.3 实现"继续编辑"功能：创建新协同创作项目并预填充历史文章内容，验证：继续编辑后新项目内容预填充正确
- [ ] 10.4 实现"删除"功能：删除前确认，验证：删除后文章从列表移除

## 11. 平台专属功能移除

- [ ] 11.1 移除 `modules/wx_publisher.py`（草稿推送模块），验证：模块文件被移除且无其他模块引用
- [ ] 11.2 移除 `modules/md_converter.py`（MD 转平台 HTML 模块），验证：模块文件被移除且无其他模块引用
- [ ] 11.3 移除 `modules/cover_generator.py` 和 `modules/cover_maker.py`（封面生成模块），验证：模块文件被移除且无其他模块引用
- [ ] 11.4 移除 `web_app.py` 中平台相关路由和菜单（平台发布、草稿箱、平台设置等），验证：相关路由不再可访问
- [ ] 11.5 移除平台相关配置文件（`domains_config.json` 等）和前端模板，验证：配置文件被移除且无引用
- [ ] 11.6 清理 `main.py` 中平台相关命令行入口和流程，验证：命令行不再展示平台相关选项

## 12. 集成测试与验收

- [ ] 12.1 执行完整协同创作流程测试：输入想法 → 生成选题 → 选择选题 → 生成大纲 → 编辑大纲 → 生成内容 → 修改内容 → 保存到历史文章，验证：全流程顺畅且保存文章包含 AI 标识
- [ ] 12.2 验证版本管理全流程：多次编辑产生多个版本 → 查看历史 → 对比版本 → 回溯版本，验证：版本记录完整且回溯正确
- [ ] 12.3 验证 AI 标识合规性：尝试保存无标识内容被阻止，管理员修改标识文案后新保存使用新文案，验证：标识强制且可配置

```

Full source: docs/openspec/changes/inkforge-collaborative-writing/tasks.md

## docs/openspec/changes/inkforge-collaborative-writing/specs/ai-content-generation/spec.md

- Source: docs/openspec/changes/inkforge-collaborative-writing/specs/ai-content-generation/spec.md
- Lines: 1-51
- SHA256: 4d816018997cdb3564ffefde7d75ff34f6435d60c97c1b2f4bd49a160f962959

```md
## Purpose

AI 内容生成能力基于已锁定大纲，支持创作者逐段生成内容或一键全部生成，生成的内容创作者可二次修改，保持对最终内容的完全控制。

## ADDED Requirements

### Requirement: 内容生成触发方式
系统 SHALL 支持两种内容生成触发方式：逐段生成（创作者点击某个大纲节点的"生成内容"）和全部生成（创作者点击"为全部大纲生成内容"），不得在创作者未触发时自动生成。

#### Scenario: 逐段生成内容
- **WHEN** 创作者点击某个大纲章节的"生成内容"
- **THEN** 系统调用 AI 基于该章节的标题和要点生成段落内容

#### Scenario: 全部生成内容
- **WHEN** 创作者点击"为全部大纲生成内容"
- **THEN** 系统调用 AI 依次为每个大纲章节生成段落内容

### Requirement: 段落级内容展示
系统 SHALL 按大纲章节结构展示生成的内容，每个段落独立呈现，标注该段落对应的大纲节点。

#### Scenario: 段落结构展示
- **WHEN** 内容生成完成
- **THEN** 系统按大纲章节分组展示段落，每个段落显示正文内容和对应大纲节点标注

### Requirement: 内容二次修改
系统 SHALL 允许创作者对 AI 生成的每段内容进行二次修改（直接在编辑器内编辑），修改后的内容自动保存。

#### Scenario: 修改段落内容
- **WHEN** 创作者点击某段落并直接编辑文本
- **THEN** 系统保存修改后的内容，并更新段落状态为"已修改"

### Requirement: 单段重新生成
系统 SHALL 允许创作者对单个段落触发 AI 重新生成，无需重新生成全部内容。

#### Scenario: 重新生成单段
- **WHEN** 创作者对某段落不满意并点击"重新生成此段"
- **THEN** 系统基于大纲上下文重新生成该段落内容

### Requirement: 内容生成进度
系统 SHALL 显示内容生成整体进度（已生成/总章节数量），帮助创作者把控全局。

#### Scenario: 查看内容进度
- **WHEN** 创作者在内容生成环节
- **THEN** 系统显示进度指示器，如"已生成 5/8 段"

### Requirement: 进入保存环节
系统 SHALL 在所有章节都生成内容后，允许创作者进入保存到历史文章环节。

#### Scenario: 完成内容进入保存
- **WHEN** 创作者处理完所有段落并点击"保存到历史文章"
- **THEN** 系统汇总所有段落为完整文章，进入保存环节

```

## docs/openspec/changes/inkforge-collaborative-writing/specs/ai-content-labeling/spec.md

- Source: docs/openspec/changes/inkforge-collaborative-writing/specs/ai-content-labeling/spec.md
- Lines: 1-47
- SHA256: 87893f92cc75ddc192c82ad984e1e4093b926e7865222ae15985a1df8c88352d

```md
## Purpose

AI 内容标识能力确保所有保存到历史文章的内容强制附加显式 AI 生成声明，满足《人工智能生成合成内容标识办法》合规要求，创作者无法删除或关闭该标识。

## ADDED Requirements

### Requirement: 强制 AI 标识
系统 SHALL 在所有保存到历史文章的内容末尾自动附加 AI 生成声明，创作者不可删除、不可关闭、不可隐藏该标识。

#### Scenario: 保存文章包含 AI 标识
- **WHEN** 创作者点击"保存到历史文章"
- **THEN** 系统自动在文章末尾附加声明："本文由 AI 辅助生成，请仔细甄别文章内容。"

### Requirement: 标识内容可配置
系统 SHALL 允许管理员配置 AI 标识的具体文案（默认："本文由 AI 辅助生成，请仔细甄别文章内容。"），但创作者无权修改标识文案。

#### Scenario: 管理员修改标识文案
- **WHEN** 管理员在系统设置中修改 AI 标识文案
- **THEN** 所有后续保存使用新文案，已保存文章保持原样

### Requirement: 标识位置固定
系统 SHALL 将 AI 标识固定在文章末尾（正文与结尾签名之间），创作者不可调整标识位置。

#### Scenario: 标识位置展示
- **WHEN** 创作者查看历史文章
- **THEN** AI 标识显示在文章正文之后、结尾签名之前

### Requirement: 标识不可绕过
系统 SHALL 在保存文章流程中强制校验 AI 标识存在，若标识缺失或为空则阻止保存并提示创作者。

#### Scenario: 标识缺失阻止保存
- **WHEN** 系统检测到保存内容缺少 AI 标识
- **THEN** 系统阻止保存并提示"AI 标识缺失，无法保存"

### Requirement: 标识样式区分
系统 SHALL 以视觉区分方式展示 AI 标识（如斜体、小字号、分隔线），使标识与正文明显区分。

#### Scenario: 标识视觉样式
- **WHEN** 文章展示 AI 标识
- **THEN** 标识以分隔线隔开，使用较小字号和斜体显示

### Requirement: 合规审计日志
系统 SHALL 记录每次保存文章时的 AI 标识状态（文案内容、位置、时间），供合规审计使用。

#### Scenario: 审计日志记录
- **WHEN** 文章保存成功
- **THEN** 系统记录文章 ID、标识文案、保存时间到审计日志

```

## docs/openspec/changes/inkforge-collaborative-writing/specs/ai-outline-generation/spec.md

- Source: docs/openspec/changes/inkforge-collaborative-writing/specs/ai-outline-generation/spec.md
- Lines: 1-44
- SHA256: 1a00b80b6e318829429f921ec73a7b090afbd3e7cf6f970530a38e59120c3408

```md
## Purpose

AI 大纲生成能力让创作者基于已确认的选题，AI 生成结构化大纲供创作者编辑、增删、重排，作为后续内容生成的基础骨架。

## ADDED Requirements

### Requirement: 大纲生成触发
系统 SHALL 允许创作者基于已确认的选题主动触发 AI 生成大纲，不得在创作者未触发时自动生成。

#### Scenario: 创作者触发生成大纲
- **WHEN** 创作者确认选题"AI 如何改变课堂教学"并点击"生成大纲"
- **THEN** 系统调用 AI 基于选题返回结构化大纲（包含章节标题、要点列表）

### Requirement: 大纲结构化输出
AI 生成的大纲 SHALL 包含层级化的章节结构（至少支持一级章节和二级要点），每个节点可独立编辑。

#### Scenario: 大纲结构展示
- **WHEN** AI 完成大纲生成
- **THEN** 系统展示可折叠的章节树，每个章节包含标题和若干要点子节点

### Requirement: 大纲编辑能力
系统 SHALL 允许创作者对 AI 生成的大纲进行编辑：修改节点标题、增删节点、调整节点顺序、移动节点层级。

#### Scenario: 编辑大纲节点
- **WHEN** 创作者双击某个大纲节点标题
- **THEN** 系统进入编辑模式，创作者可修改标题内容并保存

#### Scenario: 增加新章节
- **WHEN** 创作者点击"添加章节"
- **THEN** 系统在指定位置插入新节点，创作者输入标题后大纲更新

### Requirement: 大纲重新生成
系统 SHALL 允许创作者在编辑过程中随时触发 AI 重新生成大纲（可基于当前编辑状态作为上下文）。

#### Scenario: 重新生成大纲
- **WHEN** 创作者对当前大纲不满意并点击"重新生成"
- **THEN** 系统基于选题和当前大纲上下文生成新的大纲版本

### Requirement: 大纲锁定
系统 SHALL 提供大纲锁定机制，创作者锁定大纲后进入内容生成环节，锁定后大纲作为后续步骤的固定上下文。

#### Scenario: 锁定大纲
- **WHEN** 创作者点击"大纲完成，进入内容生成"
- **THEN** 系统锁定当前大纲状态，作为内容生成的输入上下文

```

## docs/openspec/changes/inkforge-collaborative-writing/specs/ai-topic-generation/spec.md

- Source: docs/openspec/changes/inkforge-collaborative-writing/specs/ai-topic-generation/spec.md
- Lines: 1-44
- SHA256: 6737c53d0a21c547f784d8606e354f36986e9357608500e09ed1b4c717d6bc73

```md
## Purpose

AI 选题生成能力让创作者输入一个想法（一句话/关键词/简短描述），AI 生成多个选题建议供创作者选择，作为后续大纲生成和内容生成的起点。

## ADDED Requirements

### Requirement: 选题生成触发
系统 SHALL 允许创作者输入一个想法（一句话/关键词/简短描述）并主动触发 AI 生成选题，不得在创作者未触发时自动生成。

#### Scenario: 创作者触发生成选题
- **WHEN** 创作者输入想法"AI 在教育领域的应用"并点击"生成选题"
- **THEN** 系统调用 AI 返回多个选题建议（至少 3 个），每个选题包含标题和简要说明

### Requirement: 选题建议展示
系统 SHALL 以卡片列表形式展示 AI 生成的选题建议，每个选题显示标题和简要说明，创作者可单选。

#### Scenario: 选题卡片展示
- **WHEN** AI 完成选题生成
- **THEN** 系统展示选题卡片列表，每个卡片包含选题标题（如"AI 如何改变课堂教学"）和一句话说明

### Requirement: 选题选择与确认
系统 SHALL 允许创作者选择一个选题并确认，确认后选题作为后续大纲生成的固定输入。

#### Scenario: 选择选题
- **WHEN** 创作者点击某个选题卡片并点击"选择此选题"
- **THEN** 系统锁定该选题，进入大纲生成环节

### Requirement: 选题修改与自定义
系统 SHALL 允许创作者在 AI 生成的选题基础上修改标题和说明，也允许完全自定义选题（跳过 AI 生成）。

#### Scenario: 修改 AI 生成的选题
- **WHEN** 创作者点击某个选题的"修改"
- **THEN** 系统进入编辑模式，创作者可修改标题和说明

#### Scenario: 自定义选题
- **WHEN** 创作者点击"自定义选题"并输入标题和说明
- **THEN** 系统使用创作者自定义的选题进入大纲生成环节

### Requirement: 选题重新生成
系统 SHALL 允许创作者在浏览选题过程中随时触发 AI 重新生成选题列表（可基于当前想法作为上下文）。

#### Scenario: 重新生成选题
- **WHEN** 创作者对当前选题列表不满意并点击"重新生成"
- **THEN** 系统基于想法和当前上下文生成新的选题列表

```

## docs/openspec/changes/inkforge-collaborative-writing/specs/article-history/spec.md

- Source: docs/openspec/changes/inkforge-collaborative-writing/specs/article-history/spec.md
- Lines: 1-47
- SHA256: 603cfb89593d2c52135634a5e1b2b2daaa066cb290ba6d1ef6efdeb5eed79db9

```md
## Purpose

历史文章管理能力让创作者将完成的创作保存为历史文章，支持查看、继续编辑、版本回溯，保留完整的创作成果库。

## ADDED Requirements

### Requirement: 保存到历史文章
系统 SHALL 允许创作者将完成的创作（选题、大纲、全部内容）保存到历史文章，保存时自动附加 AI 标识。

#### Scenario: 保存创作到历史文章
- **WHEN** 创作者点击"保存到历史文章"并输入文章标题
- **THEN** 系统将当前创作保存为历史文章，自动附加 AI 标识，文章出现在历史文章列表

### Requirement: 历史文章列表
系统 SHALL 为每位创作者维护历史文章列表，按保存时间倒序展示，每篇文章显示标题、保存时间、字数。

#### Scenario: 查看历史文章列表
- **WHEN** 创作者进入历史文章页面
- **THEN** 系统展示该创作者的所有历史文章，按保存时间倒序排列

### Requirement: 历史文章查看
系统 SHALL 允许创作者查看任意历史文章的完整内容（选题、大纲、正文、AI 标识），以只读模式呈现。

#### Scenario: 查看历史文章
- **WHEN** 创作者点击某篇历史文章
- **THEN** 系统展示该文章的完整内容，包括标题、正文和末尾 AI 标识

### Requirement: 历史文章继续编辑
系统 SHALL 允许创作者从历史文章继续编辑（创建新的协同创作项目，预填充历史文章的内容），修改后重新保存。

#### Scenario: 继续编辑历史文章
- **WHEN** 创作者点击某篇历史文章的"继续编辑"
- **THEN** 系统创建新的协同创作项目，预填充该历史文章的选题、大纲和内容

### Requirement: 历史文章删除
系统 SHALL 允许创作者删除不再需要的历史文章，删除前要求确认。

#### Scenario: 删除历史文章
- **WHEN** 创作者点击某篇历史文章的"删除"并确认
- **THEN** 系统将该文章从历史文章列表中移除

### Requirement: AI 标识持久化
系统 SHALL 确保历史文章中的 AI 标识持久存在，创作者查看和继续编辑时标识始终显示，不可删除。

#### Scenario: 历史文章 AI 标识展示
- **WHEN** 创作者查看历史文章
- **THEN** AI 标识显示在文章末尾，创作者无法删除或隐藏

```

## docs/openspec/changes/inkforge-collaborative-writing/specs/collaborative-workbench/spec.md

- Source: docs/openspec/changes/inkforge-collaborative-writing/specs/collaborative-workbench/spec.md
- Lines: 1-44
- SHA256: 3af6eedb7b55453f62a943f02b58f5afe42eab73c1137204aa4bd6e236e2bc5b

```md
## Purpose

人机协同创作工作台是创作者与 AI 协作写作的核心编排层，负责驱动"想法 → 选题 → 大纲 → 内容 → 保存到历史文章"的创作流程状态机，管理创作者与 AI 建议之间的交互节奏。

## ADDED Requirements

### Requirement: 创作流程编排
系统 SHALL 按照"想法输入 → 选题生成 → 大纲生成 → 内容生成 → 保存到历史文章"的顺序编排创作流程，创作者在每个环节完成后主动推进到下一环节。

#### Scenario: 正常流程推进
- **WHEN** 创作者完成选题选择并点击"进入大纲生成"
- **THEN** 系统锁定选题状态并进入大纲生成环节

#### Scenario: 跳过可选环节
- **WHEN** 创作者在选题环节选择"跳过选题，直接输入自定义选题"
- **THEN** 系统允许跳过选题生成环节，使用创作者自定义选题进入大纲生成

### Requirement: AI 交互节奏控制
系统 SHALL 在每个环节呈现 AI 建议前等待创作者主动触发（如点击"生成选题"按钮），不得自动执行 AI 生成。

#### Scenario: 创作者主动触发 AI
- **WHEN** 创作者输入想法后点击"AI 生成选题"
- **THEN** 系统调用 AI 生成并展示选题建议列表，同时显示"选择此选题/修改/重新生成"操作

### Requirement: 创作状态持久化
系统 SHALL 保存创作流程的当前状态（选题、大纲内容、各段内容、编辑状态），创作者离开后可返回继续创作。

#### Scenario: 中断后恢复创作
- **WHEN** 创作者关闭浏览器后重新打开协同创作页面
- **THEN** 系统恢复上次创作状态，创作者可从中断环节继续

### Requirement: 与现有账号体系共用
系统 SHALL 复用现有用户认证、账号管理和数据库会话，创作者无需额外注册或登录。

#### Scenario: 现有用户访问协同创作
- **WHEN** 已登录用户导航到协同创作页面
- **THEN** 系统识别当前用户身份，加载该用户的创作列表与权限

### Requirement: 创作列表与历史文章管理
系统 SHALL 为每位创作者提供协同创作项目列表和历史文章列表，支持新建、继续创作、查看历史文章。

#### Scenario: 查看创作项目
- **WHEN** 创作者进入协同创作工作台首页
- **THEN** 系统展示该创作者的所有协同创作项目（进行中）和历史文章（已完成），按最近修改时间排序

```

## docs/openspec/changes/inkforge-collaborative-writing/specs/version-management/spec.md

- Source: docs/openspec/changes/inkforge-collaborative-writing/specs/version-management/spec.md
- Lines: 1-47
- SHA256: 95bd27be50cc4fe4ddcf413ff9629899668eb7271ea988c6c4c0704b63ebb5db

```md
## Purpose

版本管理能力记录人机协同写作过程中的关键节点快照，支持创作者回溯历史版本、对比差异，保留完整的创作演进轨迹。

## ADDED Requirements

### Requirement: 自动版本快照
系统 SHALL 在创作关键节点自动创建版本快照：选题确认时、大纲锁定完成时、内容全部生成时、保存到历史文章时。

#### Scenario: 选题确认触发版本快照
- **WHEN** 创作者确认选题进入大纲生成
- **THEN** 系统自动创建版本快照，记录当前选题状态和时间戳

### Requirement: 手动版本标记
系统 SHALL 允许创作者在任何时刻手动创建命名版本标记（如"客户反馈前版本"），便于后续定位关键版本。

#### Scenario: 手动创建版本标记
- **WHEN** 创作者点击"标记版本"并输入名称"初稿完成"
- **THEN** 系统创建带名称的版本快照，出现在版本历史中

### Requirement: 版本历史浏览
系统 SHALL 为每个创作项目维护版本历史列表，按时间倒序展示，每个版本显示创建时间、版本名称、变更摘要。

#### Scenario: 查看版本历史
- **WHEN** 创作者点击"版本历史"
- **THEN** 系统展示版本列表，如"2026-08-31 15:30 - 内容生成完成 - 完成全部 8 段内容"

### Requirement: 版本内容查看
系统 SHALL 允许创作者查看任意历史版本的完整内容（选题、大纲、内容状态），以只读模式呈现。

#### Scenario: 查看历史版本
- **WHEN** 创作者点击某个历史版本
- **THEN** 系统以只读模式展示该版本的选题、大纲和内容

### Requirement: 版本对比
系统 SHALL 允许创作者选择两个版本进行差异对比，高亮显示新增、删除、修改的内容。

#### Scenario: 对比两个版本
- **WHEN** 创作者选择版本 A 和版本 B 并点击"对比"
- **THEN** 系统展示差异视图，高亮显示两版本之间的文本变化

### Requirement: 版本回溯
系统 SHALL 允许创作者将创作内容回溯到某个历史版本（创建新版本，内容为所选历史版本的内容），不丢失后续版本历史。

#### Scenario: 回溯到历史版本
- **WHEN** 创作者选择某个历史版本并点击"回溯到此版本"
- **THEN** 系统创建新版本，内容复制自所选历史版本，版本历史完整保留

```
