# 验证报告：inkforge-collaborative-writing

**日期：** 2026-09-01
**验证模式：** full（任务数 47 > 3，delta spec 能力数 7 > 1）
**产物语言：** zh-CN
**验证依据（新鲜证据）：** `python -m pytest tests/ -q` → 58 passed in 1.56s（15 测试文件）

## 摘要

| 维度 | 状态 |
|------|------|
| 完整性（Completeness） | 47/47 任务完成，0 未完成 |
| 正确性（Correctness） | 35/39 需求已实现，4 项存在偏差 |
| 一致性（Coherence） | 基本遵循设计，2 项轻微偏差 |

## 一、完整性（Completeness）

### 任务完成
- `docs/openspec/changes/inkforge-collaborative-writing/tasks.md`：**47/47 项勾选**（1.1–12.5），0 项未完成。✅
- OpenSpec `applyRequires`（proposal/specs/design/tasks）全部 `done`。✅

### 规格覆盖
7 个 delta spec 能力，共 **39 项需求、43 个场景**：

| 规格 | 需求数 | 场景数 |
|------|--------|--------|
| collaborative-workbench | 5 | 6 |
| ai-topic-generation | 5 | 6 |
| ai-outline-generation | 5 | 6 |
| ai-content-generation | 6 | 7 |
| ai-content-labeling | 6 | 6 |
| version-management | 6 | 6 |
| article-history | 6 | 6 |

## 二、正确性（Correctness）——需求实现对照

### 已验证实现（关键证据）

**协同创作工作台（collaborative-workbench）**
- 流程编排：`/collaborative`（list, L2817）、`POST /create`（L2828）、`GET /<id>`（L2853）+ workbench 页 L2972。✅
- 创作状态持久化：`GET/POST /api/collaborative/<id>/state`（L2874）。✅
- 工作台四阶段导航（选题/大纲/内容/保存）+ 版本历史侧边栏：`templates/collaborative/workbench.html` L95–99、`aside.version-sidebar` L212。✅
- 创作列表 + 历史文章管理：`templates/collaborative/list.html`、`web_static/collaborative.js`（`loadHistoryArticles`/`viewArticle`/`continueArticle`/`deleteArticle`）。✅

**AI 辅助能力（ai-writer）**
- `generate_topics`（`modules/ai_writer.py:818`）、`generate_outline`、`generate_content`（L890）：均走 `_detect_llm_backend`（L75）→ openai/ollama/template 三路 fallback。✅
- 前端触发：`generateTopics`（workbench.html:369）、`confirmTopic`（L467）、`switchPhase`（L495）、`generateOutline`（L555）、`generateContent`（L1022）。✅
- 逐段 + 全部生成：`web_app.py` `api_collaborative_generate_content`（L3028）接受 `section` 参数。✅
- 自定义选题：`toggleCustomTopic()` + `#custom-topic-form`（workbench.html:113）。✅
- 选题卡片展示 + 选择/修改：`generateTopics` 渲染卡片列表。✅

**AI 标识（ai-content-labeling）— 核心合规**
- 强制附加 + 不可绕过：`ai_labeler.attach_label`（`modules/ai_labeler.py:27`，幂等）+ `validate_content`（L36）；`save_article`（`modules/article_history.py:13`）先 attach 再 validate，缺失抛 ValueError。✅
- 管理员可配置、创作者不可改：`set_label_text`（L41）非 admin 抛 `PermissionError`。✅
- 标识位置固定（文章末尾）：`attach_label` 文案追加到内容末尾。✅
- 标识视觉样式：`web_static/common.css:1947` `.history-view-ai-label` — 分隔线（`border-top:1px dashed`）+ 小字号（13px）+ 颜色区分。⚠️ 缺少斜体（见下方偏差）。
- 保存文章含标识：`POST /api/collaborative/<id>/save-article`（web_app.py:2925）。✅

**版本管理（version-management）**
- 版本快照函数：`version_manager.create_snapshot`（L5）、`list_versions`（L23）、`get_version`（L39）、`compare_versions`（L53）、`rollback_to_version`（L62）。✅
- 自动快照上限 20：`_cap_auto_snapshots`（L77）。✅
- 版本历史浏览/查看/对比/回溯前端：`viewVersion`（workbench.html:1325）、`compareSelectedVersions`、`rollbackCurrentVersion`、版本列表 `loadVersionHistory`。✅
- 版本 API：`list_versions`/`get_version`/`compare_versions`/`rollback_version`（web_app.py:3062–3135）。✅

**历史文章（article-history）**
- `save_article`/`list_articles`/`get_article`/`update_article`/`delete_article`（`modules/article_history.py`）。✅
- 继续编辑（预填充）：`continueArticle`（collaborative.js:146）+ `test_continue_creates_prefilled_project`。✅
- 查看含 AI 标识：`viewArticle`（collaborative.js:117）渲染 `.history-view-ai-label`。✅

**平台专属功能移除（用户核心约束）**
- 4 个模块已删除：`wx_publisher.py`、`md_converter.py`、`cover_generator.py`、`cover_maker.py`（均不存在）。✅
- 活动源码无 `微信/公众号/weixin/api.weixin` 标记（仅 `templates/wechat_style.css` 残留模板文件名）。✅
- 测试覆盖：`tests/test_platform_removal.py`（3 项）+ `test_e2e_collaborative.test_e2e_platform_removed`。✅

## 偏差（Issues）

### IMPORTANT（建议修复）

**ISSUE-1：合规审计日志未实现**
- **规格：** `ai-content-labeling/spec.md` Requirement「合规审计日志」（行 42–47）：系统 SHALL 记录每次保存文章时的 AI 标识状态（文案内容、位置、时间），供合规审计使用。
- **现状：** 无任何审计日志实现——`modules/` 中无 `audit/审计` 字符串、无审计表、`save_article` 仅把 `ai_label` 写入文章自身列（`article_history` 表行 28），未写入独立审计轨迹；也无对应测试。
- **影响：** 《人工智能生成合成内容标识办法》合规审计要求未完整满足。文章记录虽包含 `ai_label` + `created_at`（可追溯文案与时间），但缺少规格要求的独立审计日志与「位置」记录。
- **建议：** 在 `save_article` 中追加审计日志写入（新建 `ai_label_audit` 表或在现有表增设审计列），并补测试 `test_save_article_writes_audit_log`。
- **证据：** `grep -rni "audit\|审计" modules/` 空；`save_article` 仅 `INSERT INTO article_history`（`modules/article_history.py:13–45`）。

**ISSUE-2：自动版本快照触发器未接入工作流**
- **规格：** `version-management/spec.md` Requirement「自动版本快照」（行 9–12）：选题确认时、大纲锁定完成时、内容全部生成时、保存到历史文章时自动创建版本快照。
- **现状：** `version_manager.create_snapshot` 仅被 `rollback_to_version` 内部调用（`modules/version_manager.py:68`）；`web_app.py` 全文件无 `create_snapshot`/`trigger_type` 引用；`save-state`（L2874）、`save-article`（L2925）路由均不触发快照。
- **影响：** 创作关键节点无自动快照，版本历史仅靠回溯时被动生成，规格要求的「自动记录人机协同过程」未实现。
- **建议：** 在 `api_collaborative_save_state` 中，当 `current_phase` 变为 `outline`/`content`/`save` 时调用 `create_snapshot(..., trigger_type="auto")`；并在 `save-article` 中补一次最终快照。
- **证据：** `grep -n "create_snapshot" web_app.py` 空；`grep -rn "create_snapshot" . --include="*.py"` 仅 `version_manager.py:68`。

### SUGGESTION（可选改进）

**ISSUE-3：手动版本标记（标记版本）未实现**
- **规格：** `version-management/spec.md` Requirement「手动版本标记」（行 21–25）：创作者可在任何时刻手动创建命名版本标记（如「客户反馈前版本」）。
- **现状：** 前端无「标记版本」按钮/函数（`grep -rni "标记版本\|markVersion" templates/ web_static/` 空）；版本快照仅由自动触发或回溯生成。
- **影响：** 创作者无法自主标记关键版本，只能依赖系统自动节点。
- **建议：** 在版本工具栏添加「标记版本」按钮 → 调 POST `/api/collaborative/<id>/versions`（`create_snapshot(..., trigger_type="manual")`）。
- **严重度说明：** 自动快照触发器（ISSUE-2）修复后，手动标记仅需前端按钮 + 复用同一 API，工作量小，故定为 SUGGESTION。

**ISSUE-4：AI 标识样式缺少斜体**
- **规格：** `ai-content-labeling/spec.md` Requirement「标识样式区分」（行 35–37）：标识应以分隔线隔开、使用较小字号和**斜体**显示。
- **现状：** `web_static/common.css:1947` `.history-view-ai-label` 实现了分隔线（`border-top:1px dashed`）+ 小字号（13px），但**未设置 `font-style:italic`**。
- **建议：** `.history-view-ai-label` 追加 `font-style: italic;`。

## 三、一致性（Coherence）

### 设计遵循
- 数据库访问统一走 `UserDB` + `_connect()` 模式（Ruling 已落实）。✅
- LLM 调用统一走 `_detect_llm_backend` → `_call_openai`/`_call_ollama`，无 API key 走内置模板 fallback。✅
- 登录态复用 `_get_session_id()` + `get_current_user()`，无会话返回 401。✅
- 标识由后端 `save-article` 强制附加并校验，前端不可绕过。✅
- 自动快照保留最近 20 个（`_cap_auto_snapshots` L77），符合设计文档 L81 风险缓解策略。✅

### 设计文档轻微偏差
- `design.md` 未明确列出自动快照的触发节点（仅 L81 提及保留策略）——属规格级缺口，非实现矛盾，建议 design doc 追加「Implementation Divergence」说明或在归档时补记。

## 四、测试覆盖证据

**新鲜运行（本消息内执行）：** `python -m pytest tests/ -q` → **58 passed in 1.56s**，15 测试文件。

| 测试文件 | 覆盖规格/场景 |
|----------|--------------|
| test_user_db_tables.py (4) | 1.1/1.2 四张表 + ai_label_config 默认行 |
| test_version_manager.py (6) | 1.3/版本 CRUD、对比、回溯、20 上限 |
| test_ai_writer_collab.py | 2.1–2.4 选题/大纲/内容生成 + fallback |
| test_ai_labeler.py | 3.1/3.2 附加/校验/管理员配置/非管理员拒绝 |
| test_article_history.py | 4.1–4.3 保存含标识、校验阻止、列表、删除 |
| test_collaborative_api.py | 5.1/5.4 路由 + 状态持久化 |
| test_collaborative_topics.py | 6.1–6.4 选题卡片/自定义/确认触发 |
| test_collaborative_outline.py | 7.1–7.3 大纲生成/编辑/锁定 |
| test_collaborative_content.py | 8.1–8.5 逐段/全部生成、二次修改、进度 |
| test_collaborative_versions.py | 9.1–9.4 版本历史/查看/对比/回溯 + 所有权 |
| test_collaborative_history_frontend.py (5) | 10.1–10.4 列表/查看/继续/删除 + 所有权 |
| test_e2e_collaborative.py (6) | 12.1–12.5 全流程/版本周期/标识合规/历史/平台移除 |
| test_platform_removal.py (3) | 11.x 模块/路由/菜单移除 |

**场景覆盖说明：** 43 个规格场景中，核心成功场景与关键边界场景（400/401/404 负向、所有权隔离、版本排序、回溯保留历史、标识缺失阻止保存、非管理员拒绝改标识）均有测试断言覆盖。未独立覆盖的场景多为 ISSUE-1/2/3 对应的缺失功能本身（审计日志、自动快照触发、手动标记）。

## 五、最终评估

**2 项 IMPORTANT 偏差、2 项 SUGGESTION 偏差；无 CRITICAL 偏差。**

- 完整性无问题（47/47 任务、全部 artifact 完成）。
- 正确性方面，用户核心约束（通用化定位、平台移除、强制 AI 标识不可绕过）均已实现并通过测试；合规审计日志（ISSUE-1）与自动快照触发（ISSUE-2）属规格明确要求的遗漏，建议归档前修复或记录接受偏差。
- 一致性方面，实现基本遵循设计文档与全局约束。

**结论：** 无阻塞性 CRITICAL 问题。ISSUE-1（合规审计日志）与 ISSUE-2（自动快照触发）为规格明确需求，建议在归档前修复；若选择接受偏差，须在报告中记录原因与影响范围。ISSUE-3/4 为低优先级改进，可归档后处理。
