---
comet_change: inkforge-collaborative-writing
role: technical-design
canonical_spec: openspec
archived-with: 2026-09-01-inkforge-collaborative-writing
status: final
---

# 墨锻工坊（inkForge-studio）人机协同创作工作台 — 技术设计

## 1. 概述

本设计文档是对 OpenSpec `design.md` 的深度技术细化，描述"人机协同创作工作台"的技术实现方案。新工作台驱动"想法 → 选题 → 大纲 → 内容 → 保存到历史文章"的创作流程，创作者全程主导决策，AI 仅作为辅助建议者。

## 2. 整体架构

### 2.1 组件图

```
┌─────────────────────────────────────────────────────────┐
│                    现有 Flask 应用                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │         web_app.py（新增 collaborative 蓝图）       │  │
│  │   GET  /collaborative/          → 创作列表         │  │
│  │   POST /collaborative/create    → 新建项目         │  │
│  │   GET  /collaborative/<id>      → 工作台           │  │
│  │   POST /api/collaborative/*     → AI 交互 API      │  │
│  └──────────────────────────────────────────────────┘  │
│                          │                              │
│  ┌───────────────┬───────┴────────┬──────────────────┐  │
│  │               │                │                  │  │
│  ▼               ▼                ▼                  ▼  │
│  ai_writer   version_mgr    article_history    ai_labeler│
│  (拆分)         (新增)         (新增)           (新增)  │
│  │                                                  │  │
│  └──────────────┬───────────────────────────────────┘  │
│                 │                                       │
│                 ▼                                       │
│            user_db.py（新增 4 表）                       │
└─────────────────────────────────────────────────────────┘
```

### 2.2 组件职责

| 组件 | 文件 | 职责 |
|---|---|---|
| 路由编排 | `web_app.py`（新增蓝图） | 路由注册、会话校验、请求响应 |
| AI 写作 | `modules/ai_writer.py`（拆分） | `generate_topics()` / `generate_outline()` / `generate_content()` |
| 版本管理 | `modules/version_manager.py`（新增） | 版本快照 CRUD、对比、回溯 |
| 历史文章 | `modules/article_history.py`（新增） | 历史文章 CRUD |
| AI 标识 | `modules/ai_labeler.py`（新增） | 标识附加、校验、管理员配置 |
| 数据访问 | `user_db.py`（扩展） | 新增 4 张表的数据库操作 |

### 2.3 AI 交互方式

**采用同步 POST + 前端加载状态（方案 A）**：
- 前端发 POST 请求，后端同步调用 LLM
- 前端显示"生成中..."加载动画
- Flask 请求超时设置为 120s
- 超时返回明确错误提示，创作者可重试

**选择理由**：与现有 Flask 技术栈一致，实现最快，MVP 优先。

## 3. 数据模型

### 3.1 协同创作项目表

```sql
CREATE TABLE collaborative_projects (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT,
    current_phase TEXT NOT NULL DEFAULT 'topic',
    topic_json TEXT,
    outline_json TEXT,
    content_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- `current_phase`：`topic` / `outline` / `content` / `save`
- `topic_json`：`{idea, selected_topic, custom_topic}`
- `outline_json`：`{sections:[{id, title, points:[], children:[]}]}`
- `content_json`：`{sections:[{id, title, content, status}]}`

### 3.2 历史文章表

```sql
CREATE TABLE article_history (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    topic_json TEXT,
    outline_json TEXT,
    content_json TEXT,
    ai_label TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- `ai_label` 保存标识文案**快照**，管理员后续修改文案不影响已保存文章

### 3.3 版本快照表

```sql
CREATE TABLE version_snapshots (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES collaborative_projects(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    version_name TEXT,
    content_json TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- `trigger_type`：`auto_topic` / `auto_outline` / `auto_content` / `auto_save` / `manual`
- `content_json` 保存完整项目状态（topic + outline + content），支持完整回溯
- 自动快照保留最近 20 个，更早仅保留关键节点；手动标记无限制

### 3.4 AI 标识配置表

```sql
CREATE TABLE ai_label_config (
    id INTEGER PRIMARY KEY,
    label_text TEXT NOT NULL DEFAULT '本文由 AI 辅助生成，请仔细甄别文章内容。',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER REFERENCES users(id)
);
```

- 单条记录，管理员可更新 `label_text`

## 4. API 设计

### 4.1 协同创作 REST API

| 方法 | 路径 | 功能 | 请求体 | 响应 |
|---|---|---|---|---|
| GET | `/api/collaborative/projects` | 获取当前用户创作列表 | — | `{projects: [...]}` |
| POST | `/api/collaborative/projects` | 新建创作项目 | `{title}` | `{project_id}` |
| GET | `/api/collaborative/<id>` | 获取项目状态 | — | `{phase, topic, outline, content}` |
| POST | `/api/collaborative/<id>/generate-topics` | AI 生成选题 | `{idea}` | `{topics: [{title, description}]}` |
| POST | `/api/collaborative/<id>/generate-outline` | AI 生成大纲 | `{topic}` | `{outline: {sections}}` |
| POST | `/api/collaborative/<id>/generate-content` | AI 生成内容 | `{outline, section_id?}` | `{sections: [{id, content}]}` |
| PUT | `/api/collaborative/<id>/topic` | 保存选题 | `{topic}` | `{success}` |
| PUT | `/api/collaborative/<id>/outline` | 保存大纲 | `{outline}` | `{success}` |
| PUT | `/api/collaborative/<id>/content` | 保存内容 | `{content}` | `{success}` |
| POST | `/api/collaborative/<id>/save-article` | 保存到历史文章 | `{title}` | `{article_id}` |
| GET | `/api/collaborative/<id>/versions` | 获取版本历史 | — | `{versions: [...]}` |
| GET | `/api/collaborative/<id>/versions/<v_id>` | 获取版本详情 | — | `{content_json}` |
| POST | `/api/collaborative/<id>/versions/compare` | 对比版本 | `{v1, v2}` | `{diff}` |
| POST | `/api/collaborative/<id>/rollback` | 回溯版本 | `{version_id}` | `{success}` |

### 4.2 关键设计决策

- AI 生成接口为 **POST**（触发动作），数据保存接口为 **PUT**（幂等更新）
- `generate-content` 的 `section_id` 可选：有则生成单段，无则生成全部
- 保存到历史文章时后端强制附加 AI 标识并校验，前端无法绕过

## 5. 前端结构

### 5.1 新增文件

```
templates/collaborative/
├── list.html          # 创作列表 + 历史文章列表
└── workbench.html     # 创作工作台（单页应用风格）

web_static/
├── collaborative.css  # 工作台样式
└── collaborative.js   # 工作台逻辑
```

### 5.2 工作台页面结构

```
┌─────────────────────────────────────────────────┐
│  ← 返回列表    协同创作：[标题]    [保存到历史文章] │
├─────────────────────────────────────────────────┤
│  ● 选题    ○ 大纲    ○ 内容    ○ 保存            │  ← 阶段导航
├─────────────────────────────────────────────────┤
│                                                 │
│  [当前阶段面板，动态加载]                         │
│                                                 │
│  选题阶段：想法输入 → 生成选题 → 选题卡片选择     │
│  大纲阶段：生成大纲 → 大纲树编辑 → 锁定          │
│  内容阶段：逐段/全部生成 → 逐段编辑 → 完成       │
│  保存阶段：输入标题 → 保存 → 附加 AI 标识        │
│                                                 │
├─────────────────────────────────────────────────┤
│  版本历史                           ▼           │  ← 侧边栏（可折叠）
│  ├─ 2026-08-31 15:30 选题确认                   │
│  ├─ 2026-08-31 15:45 大纲锁定                   │
│  └─ 2026-08-31 16:00 内容完成                   │
└─────────────────────────────────────────────────┘
```

### 5.3 关键设计决策

- 工作台为**单页多阶段**（非多页面路由），通过 JavaScript 切换阶段面板，保持创作上下文
- 阶段导航显示当前进度，已完成阶段可点击回看
- 版本历史侧边栏可折叠，不遮挡主工作区

## 6. 平台专属功能移除

### 6.1 移除模块

| 模块 | 文件 | 处理方式 |
|---|---|---|
| 草稿推送 | `modules/wx_publisher.py` | 删除文件 |
| MD 转平台 HTML | `modules/md_converter.py` | 删除文件 |
| 封面生成 | `modules/cover_generator.py` | 删除文件 |
| 封面制作 | `modules/cover_maker.py` | 删除文件 |

### 6.2 移除路由和菜单

- 移除 `web_app.py` 中平台相关路由（平台发布、草稿箱、平台设置等）
- 移除 `web_static/` 中平台相关页面（`config.html` 等）
- 移除 `main.py` 中平台相关命令行入口

### 6.3 移除配置

- 移除 `domains_config.json` 等平台相关配置文件
- 清理数据库中平台相关表字段（如有）

## 7. 关键风险与应对

| 风险 | 影响 | 应对策略 |
|---|---|---|
| LLM 调用超时 | AI 生成内容时长时间调用可能触发超时 | Flask 请求超时 120s；前端显示加载动画；超时返回明确错误 |
| 大纲 JSON 结构不一致 | AI 生成的大纲结构与前端预期不符 | 后端对 AI 输出做结构校验和补全；前端渲染时做容错处理 |
| 并发创作冲突 | 同一用户多标签页操作同一项目 | 以最后一次保存为准（简单策略）；未来可加乐观锁 |
| 版本快照膨胀 | 频繁编辑产生大量快照，数据库膨胀 | 自动快照保留最近 20 个，更早仅保留关键节点 |
| AI 标识被绕过 | 创作者通过直接调 API 绕过前端 | 后端 `save-article` 强制附加标识并校验 |
| 平台功能移除不彻底 | 代码中残留平台相关引用导致报错 | 移除前全局扫描引用；移除后运行测试确认无断裂 |

## 8. 测试策略

### 8.1 单元测试

- **工具**：pytest
- **范围**：`version_manager`、`article_history`、`ai_labeler` 各函数；`ai_writer` 三个新函数
- **LLM 处理**：mock LLM 调用，避免测试依赖外部 API

### 8.2 集成测试

- **工具**：pytest + Flask test client
- **范围**：完整创作流程端到端；版本快照/对比/回溯；AI 标识强制校验

### 8.3 手动测试

- **范围**：工作台各阶段切换；大纲编辑交互；版本历史侧边栏；加载状态显示

### 8.4 关键测试场景

1. 完整创作流程端到端（输入想法 → 保存文章，验证 AI 标识存在）
2. AI 标识合规性（尝试绕过标识保存被阻止）
3. 版本回溯正确性（回溯后内容恢复，历史不丢失）
4. 平台功能移除彻底性（无平台相关路由/模块/配置残留）
5. LLM 不可用时的降级（Ollama / 内置模板 fallback）

## 9. 与 OpenSpec 的关系

- 本设计文档是对 OpenSpec `design.md` 的**深度技术细化**，不替代或重写
- OpenSpec delta spec 仍是 canonical capability spec
- 如实现过程中发现需要补充验收场景，将回写 OpenSpec delta spec（Spec Patch）
