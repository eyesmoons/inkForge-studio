---
comet_change: coze-agent
role: technical-design
canonical_spec: openspec
archived-with: 2026-09-08-coze-agent
status: final
---

# 智能体（coze-agent）模块技术设计

## 1. Context

系统现有架构为 Flask 后端 + 原生 HTML/JS 多页面前端。各功能模块（写稿、排版、选题等）以独立 HTML 页面 + 内联 `<script>` + 共享 `common.js` 组织。公众号账号和 AI 配置存储在 SQLite 数据库中。侧边栏导航逐页复制（非共享模板），通过 `window.location.pathname` 匹配高亮当前项。

本设计是对 open 阶段 `design.md` 的深度技术细化，确认实现方案、组件边界、数据流、错误处理和测试策略。

**已确认的 Coze API 细节**（来自用户提供的工作流文档）：
- **SDK**：`cozepy`（Coze 官方 Python SDK）
- **Endpoint**：`COZE_CN_BASE_URL`（api.coze.cn）
- **认证**：`TokenAuth(token=<api_token>)`
- **Workflow ID**：`7569130427475705882`
- **输入参数**：`url`、`app_id`、`app_secret`、`prompt`
- **输出**：包含 title 和 content 两个字段（精确 key 名待实现时从 Coze 实际返回确认）

## 2. Goals / Non-Goals

**Goals:**
- 新增侧边栏「智能体」入口和独立页面
- 通过 Coze Workflow API 实现"输入链接 + 账号 + 提示词 → 改写为原创文章"
- 改写结果可一键推送到公众号草稿箱
- 复用现有账号体系（`accounts` 表）和微信发布流程（`wx_publisher` 模块）

**Non-Goals:**
- 不替换或修改现有 `ai_writer` 模块
- 不实现流式输出或多轮对话
- 不在系统内实现 Coze 工作流内部逻辑
- 不新增数据库表（复用 `accounts` 表；Coze 配置存 DB 或配置文件）

## 3. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     前端（浏览器）                        │
│                                                         │
│  agent.html（表单 + 结果展示）                            │
│    ├── url 输入框                                        │
│    ├── 账号下拉选择器（复用 loadAccounts）                 │
│    ├── prompt 输入框（默认"不要抄袭,去除AI味"）             │
│    ├── 「生成文章」按钮                                   │
│    └── 结果区（标题 + 正文 + 「推送到草稿箱」按钮）          │
│                                                         │
│  agent.css（遵循现有模块样式）                             │
│                                                         │
│  侧边栏：8 个现有页面各新增「智能体」菜单项                  │
└──────────────────────┬──────────────────────────────────┘
                       │ JSON (fetch)
┌──────────────────────▼──────────────────────────────────┐
│                   Flask 后端                             │
│                                                         │
│  /api/agent/generate  ──→  _generate_article()           │
│    ├── session 验证                                     │
│    ├── 参数校验（url, account_id, prompt）               │
│    ├── 从 DB 读取 app_id / app_secret                    │
│    └── 调用 CozeWorkflowClient.rewrite_article()         │
│                                                         │
│  /api/agent/push_draft  ──→  _push_to_draft()            │
│    ├── session 验证                                     │
│    ├── 调用 wx_publisher.WeChatPublisher                 │
│    └── 返回 media_id                                    │
│                                                         │
│  /api/coze_config (GET/PUT)  ──→  Coze 配置管理          │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              modules/coze_client.py                      │
│                                                         │
│  CozeWorkflowClient                                     │
│    ├── __init__(): 读取 workflow_id, api_token           │
│    └── rewrite_article(url, app_id, app_secret, prompt)  │
│        ├── 调用 coze.workflows.runs.run()                │
│        ├── 解析输出 → {title, content}                   │
│        └── 异常 → CozeAPIError                          │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (cozepy SDK)
┌──────────────────────▼──────────────────────────────────┐
│              Coze Workflow API (api.coze.cn)             │
│              workflow_id: 7569130427475705882            │
└─────────────────────────────────────────────────────────┘
```

## 4. Components

### 4.1 `modules/coze_client.py` — Coze SDK 封装

**职责**：隔离 Coze SDK 依赖，提供单一、可测试的工作流调用接口。

```python
class CozeAPIError(Exception):
    """Coze 调用异常"""

class CozeWorkflowClient:
    def __init__(self, workflow_id: str, api_token: str, base_url: str = COZE_CN_BASE_URL):
        self.workflow_id = workflow_id
        self._client = Coze(auth=TokenAuth(token=api_token), base_url=base_url)

    def rewrite_article(self, url: str, app_id: str, app_secret: str, prompt: str) -> dict:
        """
        调用 Coze 工作流改写文章。
        
        Returns:
            {"title": str, "content": str}
        
        Raises:
            CozeAPIError: Coze 调用失败或输出解析失败
        """
```

**设计要点**：
- 配置缺失（workflow_id / api_token 为空）时在 `__init__` 或调用时抛出 `CozeAPIError`
- 超时处理：`run()` 调用设置 60s 超时
- 输出解析：从 Coze 返回中提取 title 和 content（精确字段路径待实现时确认）
- 所有 Coze 相关异常统一转换为 `CozeAPIError`，便于后端路由统一处理

### 4.2 后端路由（`web_app.py`）

**`POST /api/agent/generate`**
- 输入：`{url: str, account_id: str, prompt: str}`
- 流程：session 验证 → 参数校验 → 从 `accounts` 表读取 app_id/app_secret → 调用 `CozeWorkflowClient` → 返回 `{title, content}`
- 错误码：400（参数错/凭证未配置）、401（未登录）、502（Coze 调用失败）、504（超时）

**`POST /api/agent/push_draft`**
- 输入：`{title: str, content: str, account_id: str}`
- 流程：session 验证 → 从 `accounts` 表读取凭证 → 调用 `wx_publisher.WeChatPublisher.publish_article()` → 返回 `{media_id}`
- 复用现有微信发布流程，不重复实现

**`GET/PUT /api/coze_config`**
- GET：返回当前 Coze 配置（workflow_id、api_token 是否存在，不返回明文 token）
- PUT：更新 Coze 配置
- 存储方式：存 DB（与 AI 模型配置并列）或系统配置文件

### 4.3 前端页面（`web_static/agent.html`）

**布局**（参照 `write.html`）：
- 左侧输入区：url 输入框 + 账号选择器 + prompt 输入框 + 生成按钮
- 右侧结果区：标题展示 + 正文展示 + 推草稿按钮

**交互流程**：
1. 页面加载 → 调用 `loadAccounts()` 填充账号选择器（默认选中默认账号）
2. 用户填写 url + prompt → 点击「生成文章」
3. 前端校验（url 非空、账号已选）→ 显示加载状态 + 禁用按钮
4. POST `/api/agent/generate` → 成功则展示结果，失败则显示错误提示
5. 用户点击「推送到草稿箱」→ POST `/api/agent/push_draft` → 提示成功/失败

**内联 `<script>`** 遵循现有约定（如 write.html），不新建独立 JS 文件。

### 4.4 侧边栏集成

- 在现有 8 个 HTML 页面（dashboard、topics、write、rewrite、import、history、schedule、config、profile）的 `<nav class="nav">` 中新增：
  ```html
  <a href="/agent.html" class="nav-item">
    <span class="icon">🤖</span> 智能体
  </a>
  ```
- 激活态逻辑已有（`window.location.pathname` 匹配），无需额外处理

### 4.5 Coze 配置管理（`config.html`）

- 新增「Coze 工作流配置」手风琴区，与「AI 大模型管理」并列
- 字段：Workflow ID 输入框、API Token 输入框（password 类型）
- 保存调用 `PUT /api/coze_config`

## 5. Data Flow

### 5.1 生成文章

```
用户输入 (url, account_id, prompt)
  │
  ▼
agent.js: 校验参数 → 显示加载状态
  │
  ▼
POST /api/agent/generate {url, account_id, prompt}
  │
  ▼
web_app.py: session 验证
  │
  ├─ 从 accounts 表读取 app_id, app_secret
  │
  ▼
CozeWorkflowClient.rewrite_article(url, app_id, app_secret, prompt)
  │
  ├─ coze.workflows.runs.run(
  │      workflow_id="7569130427475705882",
  │      parameters={"url": url, "app_id": app_id, "app_secret": app_secret, "prompt": prompt}
  │    )
  │
  ├─ 解析输出 → {title, content}
  │
  ▼
返回 JSON {title, content}
  │
  ▼
agent.js: 展示标题和正文
```

### 5.2 推送草稿

```
用户点击「推送到草稿箱」
  │
  ▼
POST /api/agent/push_draft {title, content, account_id}
  │
  ▼
web_app.py: session 验证 → 读取账号凭证
  │
  ▼
wx_publisher.WeChatPublisher(title, content, app_id, app_secret).publish_article()
  │
  ▼
返回 {media_id} → 前端提示成功
```

## 6. Error Handling

| 场景 | 前端行为 | 后端响应 |
|------|----------|----------|
| 未登录 | 跳转登录页 | 401 |
| url 为空或账号未选 | 提示填写必填项，不发起请求 | - |
| Coze 凭证未配置 | 提示"请先配置 Coze 工作流" | 400 + 明确消息 |
| Coze 调用超时（60s） | 提示"生成超时，请稍后重试" | 504 |
| Coze 返回错误 | 提示"生成失败，请重试" | 502 + 错误详情 |
| 输出解析失败 | 提示"结果解析失败" | 502 |
| 微信推送失败 | 显示微信 API 错误原因，内容保留 | 500 + 错误详情 |

## 7. Security

- **AppSecret 不暴露前端**：前端只传 `account_id`，后端从 DB 读取 app_id/app_secret
- **Coze API Token**：存 DB / 配置文件，不暴露到前端（GET 配置时返回是否存在，不返回明文）
- **session 验证**：所有 `/api/agent/*` 路由验证登录态

## 8. Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| Coze API 变更 | `coze_client.py` 封装隔离，变更只改一处 |
| 侧边栏逐页复制导致遗漏 | 实现时逐页检查，共 9 个页面（含 agent.html 自身） |
| Coze 执行时间过长 | 60s 超时 + 前端加载动画；后续可升级流式 |
| 输出字段名不匹配 | 实现时从 Coze 实际返回确认，预留适配层 |

## 9. Testing Strategy

- **单元测试**：`coze_client.py` 用 mock 测试 Coze API 调用、输出解析、异常转换
- **集成测试**：`/api/agent/generate` 路由的参数校验、session 验证、错误响应
- **端到端测试**：输入链接 → 生成 → 展示 → 推草稿 → 公众号后台确认草稿存在
- **异常测试**：空链接、Coze 超时/错误、凭证未配置、推送失败

## 10. Dependencies

- **新增 Python 包**：`cozepy`（加入 `requirements.txt`）
- **无新增数据库表**：复用 `accounts` 表

## 11. Open Questions

| 问题 | 影响 | 确认时机 |
|------|------|----------|
| Coze 输出中 title / content 的精确字段名 | `coze_client.py` 解析逻辑 | 实现时从 Coze 实际返回确认 |
| Coze 配置存储方式（DB vs 配置文件） | 后端路由设计 | 实现时决定（倾向 DB，与 AI 模型配置一致） |
