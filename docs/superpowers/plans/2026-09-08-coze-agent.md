---
change: coze-agent
design-doc: docs/superpowers/specs/2026-09-08-coze-agent-design.md
base-ref: 7c313e47cb814f02a0cf373d9eecfc50cc7b0342
archived-with: 2026-09-08-coze-agent
---

# 智能体（coze-agent）模块实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增「智能体」功能模块：用户输入文章链接 + 选择账号 + 提示词，通过 Coze Workflow API 改写为原创文章，并一键推送到公众号草稿箱。

**Architecture:** 新增 `modules/coze_client.py` 封装 Coze SDK（隔离第三方依赖），在 `web_app.py` 新增 3 个后端路由（generate / push_draft / coze_config）和 1 个页面路由（agent.html），新增前端三件套（agent.html / agent.css / agent.js），在 config.html 新增 Coze 配置手风琴区，在所有 9 个页面侧边栏新增「智能体」菜单项。Coze 配置以系统级 JSON 文件（`coze_config.json`）存储，复用现有 `accounts` 表获取公众号凭证，复用 `wx_publisher` 推草稿。

**Tech Stack:** Python 3.13 / Flask / cozepy (Coze SDK) / SQLite (via 现有 user_db) / 原生 HTML+CSS+JS（无前端框架）

**Spec:** `docs/superpowers/specs/2026-09-08-coze-agent-design.md`

## Global Constraints

- **语言**：所有用户可见字符串、代码注释、提交信息使用中文（zh-CN）
- **不修改现有模块**：不改动 `ai_writer`、`article_rewriter` 内部逻辑，仅新增文件/路由
- **不新增数据库表**：复用 `accounts` 表；Coze 配置存 `coze_config.json`（系统级，非用户级）
- **遵循现有前端约定**：侧边栏逐页复制（非共享模板），每页内联 `DOMContentLoaded` 通过 `window.location.pathname` 匹配高亮当前导航项；账号选择器使用 `loadAccounts()`（common.js）
- **遵循现有后端约定**：session 验证使用 `_get_session_id()` + `get_current_user()`；账号凭证使用 `get_account_config(account_id)`；错误响应使用 `jsonify({...}), status_code`
- **安全约束**：AppSecret 不暴露前端（前端只传 account_id）；Coze API Token 不返回明文（GET 配置只返回是否已设置）
- **新增依赖**：`cozepy` 加入 `requirements.txt`
- **cozepy 实际 API 注意**：设计文档写的是 `coze.workflows.runs.run()`，但 cozepy 实际 API 是 `coze.workflows.runs.create()`（非流式同步），返回 `WorkflowRunResult`，其 `.data` 字段为 JSON 字符串。本计划按实际 API 编写，实现时以已安装的 cozepy 为准。

---

## File Structure

### 新建文件

| 文件 | 职责 |
|------|------|
| `modules/coze_client.py` | 封装 Coze SDK，提供 `CozeWorkflowClient`、`CozeAPIError`、配置读写函数 |
| `coze_config.json` | 系统级 Coze 配置持久化（workflow_id、api_token） |
| `web_static/agent.html` | 智能体页面结构（输入区 + 结果区） |
| `web_static/agent.css` | 智能体页面样式 |
| `web_static/agent.js` | 智能体页面交互逻辑 |
| `tests/__init__.py` | 测试包标记 |
| `tests/conftest.py` | pytest 共享 fixture（Flask test_client、临时 coze_config） |
| `tests/test_coze_client.py` | coze_client 单元测试（mock cozepy） |
| `tests/test_agent_routes.py` | agent 路由集成测试 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `web_app.py` | 新增 `/api/agent/generate`、`/api/agent/push_draft`、`GET/PUT /api/coze_config`、`/agent.html` 页面路由 |
| `web_static/config.html` | 新增「Coze 工作流配置」手风琴区 |
| `web_static/dashboard.html` | 侧边栏新增「智能体」菜单项 |
| `web_static/topics.html` | 同上 |
| `web_static/write.html` | 同上 |
| `web_static/rewrite.html` | 同上 |
| `web_static/import.html` | 同上 |
| `web_static/history.html` | 同上 |
| `web_static/schedule.html` | 同上 |
| `web_static/config.html` | 同上 |
| `web_static/profile.html` | 同上 |
| `requirements.txt` | 新增 `cozepy` |

---

## Task 1: Coze 客户端模块 `modules/coze_client.py`

**Files:**
- Create: `modules/coze_client.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_coze_client.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `cozepy` (Coze, TokenAuth, SyncHTTPClient)
- Produces:
  - `CozeAPIError(Exception)` — Coze 调用/解析异常
  - `load_coze_config() -> dict` — 读取 `coze_config.json`，返回 `{"workflow_id": str, "api_token": str}`，文件不存在返回 `{}`
  - `save_coze_config(data: dict)` — 写入 `coze_config.json`
  - `CozeWorkflowClient.__init__(workflow_id: str, api_token: str, base_url: str = "https://api.coze.cn")` — 配置缺失抛 `CozeAPIError`
  - `CozeWorkflowClient.rewrite_article(url, app_id, app_secret, prompt) -> {"title": str, "content": str}` — 失败/解析失败抛 `CozeAPIError`

- [x] **Step 1: 添加 cozepy 依赖**

在 `requirements.txt` 末尾追加一行：

```
# Coze 工作流 SDK（智能体模块）
cozepy>=0.1.0
```

- [x] **Step 2: 创建测试包与共享 fixture**

创建 `tests/__init__.py`（空文件）。

创建 `tests/conftest.py`：

```python
"""pytest 共享 fixture"""
import os
import json
import tempfile
import pytest
from pathlib import Path

# 确保可导入项目模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import web_app as web_app_mod
from modules import coze_client


@pytest.fixture
def tmp_coze_config(tmp_path, monkeypatch):
    """创建临时 coze_config.json 并让 coze_client 指向它"""
    cfg = {"workflow_id": "7569130427475705882", "api_token": "test-token-xxx"}
    config_file = tmp_path / "coze_config.json"
    config_file.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(coze_client, "COZE_CONFIG_FILE", config_file)
    return config_file


@pytest.fixture
def app():
    """Flask 测试客户端"""
    web_app_mod.app.config["TESTING"] = True
    with web_app_mod.app.test_client() as client:
        yield client
```

- [x] **Step 3: 编写 coze_client 失败测试**

创建 `tests/test_coze_client.py`：

```python
"""modules/coze_client.py 单元测试"""
import json
import pytest
from unittest.mock import patch, MagicMock
from modules.coze_client import (
    CozeAPIError,
    CozeWorkflowClient,
    load_coze_config,
    save_coze_config,
)


class TestLoadCozeConfig:
    def test_load_existing_config(self, tmp_coze_config):
        data = load_coze_config()
        assert data["workflow_id"] == "7569130427475705882"
        assert data["api_token"] == "test-token-xxx"

    def test_load_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "modules.coze_client.COZE_CONFIG_FILE",
            tmp_path / "nonexistent.json",
        )
        assert load_coze_config() == {}


class TestSaveCozeConfig:
    def test_save_roundtrip(self, tmp_path, monkeypatch):
        config_file = tmp_path / "coze_config.json"
        monkeypatch.setattr("modules.coze_client.COZE_CONFIG_FILE", config_file)
        save_coze_config({"workflow_id": "123", "api_token": "abc"})
        loaded = load_coze_config()
        assert loaded["workflow_id"] == "123"
        assert loaded["api_token"] == "abc"


class TestCozeWorkflowClientInit:
    def test_missing_workflow_id_raises(self):
        with pytest.raises(CozeAPIError, match="workflow_id"):
            CozeWorkflowClient(workflow_id="", api_token="tok")

    def test_missing_api_token_raises(self):
        with pytest.raises(CozeAPIError, match="api_token"):
            CozeWorkflowClient(workflow_id="wid", api_token="")

    def test_valid_init(self):
        # 不实际调用 API，仅验证构造不抛错
        client = CozeWorkflowClient(workflow_id="wid", api_token="tok")
        assert client.workflow_id == "wid"


class TestRewriteArticle:
    def test_successful_parse(self):
        client = CozeWorkflowClient(workflow_id="wid", api_token="tok")
        # mock 内部 _client
        mock_result = MagicMock()
        mock_result.data = json.dumps({"title": "测试标题", "content": "测试正文"})
        client._client = MagicMock()
        client._client.workflows.runs.create.return_value = mock_result

        result = client.rewrite_article("http://x.com", "aid", "sec", "不要抄袭")
        assert result == {"title": "测试标题", "content": "测试正文"}

    def test_empty_data_raises(self):
        client = CozeWorkflowClient(workflow_id="wid", api_token="tok")
        mock_result = MagicMock()
        mock_result.data = ""
        client._client = MagicMock()
        client._client.workflows.runs.create.return_value = mock_result

        with pytest.raises(CozeAPIError, match="返回为空"):
            client.rewrite_article("http://x.com", "aid", "sec", "p")

    def test_invalid_json_raises(self):
        client = CozeWorkflowClient(workflow_id="wid", api_token="tok")
        mock_result = MagicMock()
        mock_result.data = "not-json-{{{"
        client._client = MagicMock()
        client._client.workflows.runs.create.return_value = mock_result

        with pytest.raises(CozeAPIError, match="解析失败"):
            client.rewrite_article("http://x.com", "aid", "sec", "p")

    def test_api_exception_wrapped(self):
        client = CozeWorkflowClient(workflow_id="wid", api_token="tok")
        client._client = MagicMock()
        client._client.workflows.runs.create.side_effect = RuntimeError("boom")

        with pytest.raises(CozeAPIError, match="调用失败"):
            client.rewrite_article("http://x.com", "aid", "sec", "p")
```

- [x] **Step 4: 运行测试确认失败**

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python -m pytest tests/test_coze_client.py -v`
Expected: 全部 FAIL（`CozeAPIError` 等未定义）

- [x] **Step 5: 实现 `modules/coze_client.py`**

```python
"""
modules/coze_client.py
Coze Workflow API 封装 —— 隔离 cozepy 第三方依赖，提供可测试的工作流调用接口。
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any

from cozepy import Coze, TokenAuth
from cozepy.request import SyncHTTPClient

# 系统级配置文件路径（与 config.json 并列）
COZE_CONFIG_FILE = Path(__file__).parent.parent / "coze_config.json"
COZE_CN_BASE_URL = "https://api.coze.cn"
REQUEST_TIMEOUT = 60  # 秒，Coze 工作流同步调用超时


class CozeAPIError(Exception):
    """Coze 调用异常（含配置缺失、API 失败、输出解析失败）"""


def load_coze_config() -> dict:
    """加载 Coze 配置。文件不存在返回空字典。"""
    if COZE_CONFIG_FILE.exists():
        with open(COZE_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_coze_config(data: dict) -> None:
    """保存 Coze 配置到 JSON 文件。"""
    with open(COZE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class CozeWorkflowClient:
    """
    Coze 工作流调用客户端。

    用法:
        client = CozeWorkflowClient(workflow_id="...", api_token="...")
        result = client.rewrite_article(url, app_id, app_secret, prompt)
        # result = {"title": str, "content": str}
    """

    def __init__(
        self,
        workflow_id: str,
        api_token: str,
        base_url: str = COZE_CN_BASE_URL,
    ):
        if not workflow_id:
            raise CozeAPIError("Coze workflow_id 未配置，请先在系统配置中设置")
        if not api_token:
            raise CozeAPIError("Coze api_token 未配置，请先在系统配置中设置")

        self.workflow_id = workflow_id
        http_client = SyncHTTPClient(timeout=REQUEST_TIMEOUT)
        self._client = Coze(
            auth=TokenAuth(token=api_token),
            base_url=base_url,
            http_client=http_client,
        )

    def rewrite_article(
        self,
        url: str,
        app_id: str,
        app_secret: str,
        prompt: str,
    ) -> Dict[str, str]:
        """
        调用 Coze 工作流改写文章。

        Returns:
            {"title": str, "content": str}

        Raises:
            CozeAPIError: Coze 调用失败或输出解析失败
        """
        try:
            result = self._client.workflows.runs.create(
                workflow_id=self.workflow_id,
                parameters={
                    "url": url,
                    "app_id": app_id,
                    "app_secret": app_secret,
                    "prompt": prompt,
                },
            )
        except CozeAPIError:
            raise
        except Exception as e:
            raise CozeAPIError(f"Coze 调用失败：{e}") from e

        if not result.data:
            raise CozeAPIError("Coze 返回为空，未包含执行结果 data")

        try:
            output = json.loads(result.data)
        except (json.JSONDecodeError, TypeError) as e:
            raise CozeAPIError(f"Coze 输出解析失败（非合法 JSON）：{e}") from e

        title = str(output.get("title", "")).strip()
        content = str(output.get("content", "")).strip()
        if not title and not content:
            raise CozeAPIError(
                "Coze 输出中未找到 title/content 字段，请确认工作流返回格式"
            )
        return {"title": title, "content": content}
```

> **实现提示**：`result.data` 中 title/content 的精确字段名需从 Coze 实际返回确认。若实际字段名不同，仅修改 `rewrite_article` 中 `output.get(...)` 的 key 即可，适配层已集中于此。

- [x] **Step 6: 运行测试确认通过**

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python -m pytest tests/test_coze_client.py -v`
Expected: 全部 PASS

- [x] **Step 7: 提交**

```bash
git add modules/coze_client.py tests/__init__.py tests/conftest.py tests/test_coze_client.py requirements.txt
git commit -m "feat: 新增 coze_client 模块封装 Coze Workflow API"
```

---

## Task 2: Coze 配置管理与 `/api/coze_config` 路由

**Files:**
- Modify: `web_app.py`
- Modify: `web_static/config.html`

**Interfaces:**
- Consumes: `coze_client.load_coze_config` / `save_coze_config`
- Produces:
  - `GET /api/coze_config` → `{"workflow_id": str, "api_token_set": bool}`（不返回明文 token）
  - `PUT /api/coze_config` body `{"workflow_id": str, "api_token": str}` → `{"ok": True}`
  - `config.html` 新增「Coze 工作流配置」手风琴区，保存调用 `PUT /api/coze_config`

- [x] **Step 1: 编写配置路由失败测试**

在 `tests/test_agent_routes.py` 新建文件并追加：

```python
"""agent 路由集成测试"""
import json
import pytest


class TestCozeConfigRoute:
    def _auth_session(self, app):
        """登录并返回带 session cookie 的 client（使用默认 admin 账号）"""
        # 直接通过设置 session 绕过登录
        with app.session_transaction() as sess:
            sess["user"] = {"id": 1, "username": "admin"}
        return app

    def test_get_config_masked(self, app, tmp_coze_config):
        app = self._auth_session(app)
        resp = app.get("/api/coze_config")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["workflow_id"] == "7569130427475705882"
        assert data["api_token_set"] is True
        # 确保不返回明文 token
        assert "api_token" not in data

    def test_get_config_empty(self, app, tmp_path, monkeypatch):
        from modules import coze_client
        monkeypatch.setattr(
            coze_client, "COZE_CONFIG_FILE", tmp_path / "none.json"
        )
        app = self._auth_session(app)
        resp = app.get("/api/coze_config")
        data = resp.get_json()
        assert data["workflow_id"] == ""
        assert data["api_token_set"] is False

    def test_put_config(self, app, tmp_coze_config):
        app = self._auth_session(app)
        resp = app.put(
            "/api/coze_config",
            data=json.dumps({"workflow_id": "999", "api_token": "new-token"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        # 验证持久化
        from modules.coze_client import load_coze_config
        cfg = load_coze_config()
        assert cfg["workflow_id"] == "999"
        assert cfg["api_token"] == "new-token"

    def test_config_requires_login(self, app):
        resp = app.get("/api/coze_config")
        assert resp.status_code == 401
```

- [x] **Step 2: 运行测试确认失败**

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python -m pytest tests/test_agent_routes.py::TestCozeConfigRoute -v`
Expected: FAIL（路由未定义）

- [x] **Step 3: 在 web_app.py 新增 `/api/coze_config` 路由**

在 `web_app.py` 顶部导入区追加：

```python
from modules.coze_client import load_coze_config, save_coze_config
```

在 `# API：配置管理` 区域（`api_save_config` 之后）追加：

```python
# ════════════════════════════════════════════════════════════
# API：Coze 工作流配置
# ════════════════════════════════════════════════════════════

@app.route("/api/coze_config", methods=["GET"])
def api_get_coze_config():
    """获取 Coze 配置（不返回明文 api_token）"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    cfg = load_coze_config()
    return jsonify({
        "workflow_id": cfg.get("workflow_id", ""),
        "api_token_set": bool(cfg.get("api_token")),
    })


@app.route("/api/coze_config", methods=["PUT"])
def api_save_coze_config():
    """保存 Coze 配置"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    workflow_id = (data.get("workflow_id") or "").strip()
    api_token = (data.get("api_token") or "").strip()

    if not workflow_id:
        return jsonify({"error": "Workflow ID 不能为空"}), 400

    save_coze_config({"workflow_id": workflow_id, "api_token": api_token})
    return jsonify({"ok": True})
```

- [x] **Step 4: 运行测试确认通过**

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python -m pytest tests/test_agent_routes.py::TestCozeConfigRoute -v`
Expected: 全部 PASS

- [x] **Step 5: 在 config.html 新增 Coze 配置手风琴区**

在 `config.html` 的 `acc-ai-models` 手风琴之后、`</div> <!-- /content -->` 之前，追加新手风琴：

```html
      <!-- Coze 工作流配置手风琴 -->
      <div class="accordion" id="acc-coze">
        <div class="accordion-header" onclick="toggleAccordion('acc-coze')">
          <span class="accordion-title">🤖 Coze 工作流配置</span>
          <span class="accordion-icon">▼</span>
        </div>
        <div class="accordion-content">
          <p style="color:var(--text2);font-size:13px;margin-bottom:16px;">
            配置 Coze 工作流用于「智能体」模块的文章改写。Workflow ID 和 API Token 可在
            <a href="https://www.coze.cn/store" target="_blank" style="color:var(--primary);">Coze 官网</a> 获取。
          </p>
          <div class="form-group form-full">
            <label class="form-label">Workflow ID</label>
            <input class="form-input" id="coze-workflow-id" type="text" placeholder="如：7569130427475705882">
          </div>
          <div class="form-group form-full">
            <label class="form-label">API Token</label>
            <input class="form-input" id="coze-api-token" type="password" placeholder="输入 Coze API Token">
          </div>
          <div style="display:flex;justify-content:flex-end;margin-top:8px;">
            <button class="btn btn-primary" onclick="saveCozeConfig()">💾 保存配置</button>
          </div>
        </div>
      </div>
```

- [x] **Step 6: 在 config.html 的 `<script>` 中追加 Coze 配置逻辑**

在 `config.html` 的 `loadConfig()` 函数内，`await loadAIModels()` 之后追加：

```javascript
  // 加载 Coze 配置
  await loadCozeConfig();
```

在 `config.html` 的 `<script>` 末尾（`</script>` 前）追加：

```javascript
async function loadCozeConfig() {
  try {
    const res = await fetch('/api/coze_config');
    const data = await res.json();
    if (data.workflow_id !== undefined) {
      document.getElementById('coze-workflow-id').value = data.workflow_id || '';
      if (data.api_token_set) {
        document.getElementById('coze-api-token').value = '********';
      }
    }
  } catch(e) {
    console.error('加载 Coze 配置失败:', e);
  }
}

async function saveCozeConfig() {
  const workflowId = document.getElementById('coze-workflow-id').value.trim();
  const apiToken = document.getElementById('coze-api-token').value.trim();

  if (!workflowId) {
    toast('请输入 Workflow ID', 'error');
    return;
  }
  // 掩码未修改时不更新 token
  const tokenToSend = apiToken === '********' ? '' : apiToken;

  try {
    const res = await fetch('/api/coze_config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow_id: workflowId, api_token: tokenToSend }),
    });
    const data = await res.json();
    if (data.ok) {
      toast('Coze 配置已保存', 'success');
      await loadCozeConfig();
    } else {
      toast(data.error || '保存失败', 'error');
    }
  } catch(e) {
    toast('保存失败：' + e.message, 'error');
  }
}
```

- [x] **Step 7: 提交**

```bash
git add web_app.py web_static/config.html
git commit -m "feat: 新增 Coze 工作流配置管理与 config 页面手风琴"
```

---

## Task 3: `/api/agent/generate` 路由

**Files:**
- Modify: `web_app.py`
- Modify: `tests/test_agent_routes.py`

**Interfaces:**
- Consumes: `coze_client.CozeWorkflowClient`, `coze_client.load_coze_config`, `web_app.get_account_config`
- Produces:
  - `POST /api/agent/generate` body `{"url": str, "account_id": str, "prompt": str}` → `{"title": str, "content": str}`
  - 错误码：401（未登录）、400（参数错/凭证未配置）、502（Coze 调用失败）、504（超时）

- [x] **Step 1: 编写 generate 路由失败测试**

在 `tests/test_agent_routes.py` 追加新类：

```python
class TestAgentGenerateRoute:
    def _auth_session(self, app):
        with app.session_transaction() as sess:
            sess["user"] = {"id": 1, "username": "admin"}
        return app

    def test_generate_requires_login(self, app):
        resp = app.post("/api/agent/generate",
                        data=json.dumps({"url": "http://x.com", "account_id": "demo"}),
                        content_type="application/json")
        assert resp.status_code == 401

    def test_generate_missing_url(self, app, tmp_coze_config):
        app = self._auth_session(app)
        resp = app.post("/api/agent/generate",
                        data=json.dumps({"url": "", "account_id": "demo"}),
                        content_type="application/json")
        assert resp.status_code == 400

    def test_generate_coze_not_configured(self, app, tmp_path, monkeypatch):
        from modules import coze_client
        monkeypatch.setattr(coze_client, "COZE_CONFIG_FILE", tmp_path / "none.json")
        app = self._auth_session(app)
        resp = app.post("/api/agent/generate",
                        data=json.dumps({"url": "http://x.com", "account_id": "demo"}),
                        content_type="application/json")
        assert resp.status_code == 400
        assert "Coze" in resp.get_json()["error"]

    def test_generate_success(self, app, tmp_coze_config, monkeypatch):
        """mock CozeWorkflowClient 验证路由返回结构"""
        app = self._auth_session(app)

        from modules import coze_client
        mock_client = MagicMock()
        mock_client.rewrite_article.return_value = {"title": "t", "content": "c"}
        monkeypatch.setattr(
            coze_client, "CozeWorkflowClient",
            lambda *a, **k: mock_client,
        )
        # mock get_account_config 返回凭证
        monkeypatch.setattr(
            "web_app.get_account_config",
            lambda *a, **k: {"app_id": "aid", "app_secret": "sec"},
        )

        resp = app.post("/api/agent/generate",
                        data=json.dumps({"url": "http://x.com", "account_id": "demo", "prompt": "p"}),
                        content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "t"
        assert data["content"] == "c"

    def test_generate_coze_error_returns_502(self, app, tmp_coze_config, monkeypatch):
        app = self._auth_session(app)
        from modules import coze_client
        mock_client = MagicMock()
        mock_client.rewrite_article.side_effect = coze_client.CozeAPIError("boom")
        monkeypatch.setattr(coze_client, "CozeWorkflowClient", lambda *a, **k: mock_client)
        monkeypatch.setattr("web_app.get_account_config",
                            lambda *a, **k: {"app_id": "aid", "app_secret": "sec"})

        resp = app.post("/api/agent/generate",
                        data=json.dumps({"url": "http://x.com", "account_id": "demo"}),
                        content_type="application/json")
        assert resp.status_code == 502
```

在文件顶部 import 区追加 `from unittest.mock import MagicMock`。

- [x] **Step 2: 运行测试确认失败**

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python -m pytest tests/test_agent_routes.py::TestAgentGenerateRoute -v`
Expected: FAIL（路由未定义）

- [x] **Step 3: 在 web_app.py 新增 `/api/agent/generate` 路由**

在导入区已有 `from modules.coze_client import load_coze_config, save_coze_config` 基础上，确认 `CozeWorkflowClient` 也导入：

```python
from modules.coze_client import (
    CozeAPIError,
    CozeWorkflowClient,
    load_coze_config,
    save_coze_config,
)
```

在 `# API：AI 生成文章` 区域之前，新增：

```python
# ════════════════════════════════════════════════════════════
# API：智能体（Coze 文章改写）
# ════════════════════════════════════════════════════════════

@app.route("/api/agent/generate", methods=["POST"])
def api_agent_generate():
    """调用 Coze 工作流改写文章，返回标题和正文"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    url = (data.get("url") or "").strip()
    account_id = (data.get("account_id") or "").strip()
    prompt = (data.get("prompt") or "不要抄袭,去除AI味").strip()

    if not url:
        return jsonify({"error": "请输入文章链接"}), 400
    if not account_id:
        return jsonify({"error": "请选择账号"}), 400

    # 加载 Coze 配置
    coze_cfg = load_coze_config()
    if not coze_cfg.get("workflow_id") or not coze_cfg.get("api_token"):
        return jsonify({"error": "请先配置 Coze 工作流（系统配置 → Coze 工作流配置）"}), 400

    # 读取账号凭证
    acc_cfg = get_account_config(account_id)
    if not acc_cfg or not acc_cfg.get("app_id") or not acc_cfg.get("app_secret"):
        return jsonify({"error": "账号未配置 AppID/AppSecret"}), 400

    try:
        client = CozeWorkflowClient(
            workflow_id=coze_cfg["workflow_id"],
            api_token=coze_cfg["api_token"],
        )
        result = client.rewrite_article(
            url=url,
            app_id=acc_cfg["app_id"],
            app_secret=acc_cfg["app_secret"],
            prompt=prompt,
        )
        return jsonify(result)
    except CozeAPIError as e:
        return jsonify({"error": f"生成失败：{e}"}), 502
    except Exception as e:
        return jsonify({"error": f"生成失败：{e}"}), 502
```

- [x] **Step 4: 运行测试确认通过**

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python -m pytest tests/test_agent_routes.py::TestAgentGenerateRoute -v`
Expected: 全部 PASS

- [x] **Step 5: 提交**

```bash
git add web_app.py tests/test_agent_routes.py
git commit -m "feat: 新增 POST /api/agent/generate 路由"
```

---

## Task 4: `/api/agent/push_draft` 路由

**Files:**
- Modify: `web_app.py`
- Modify: `tests/test_agent_routes.py`

**Interfaces:**
- Consumes: `modules.wx_publisher.WeChatPublisher`, `web_app.get_account_config`
- Produces:
  - `POST /api/agent/push_draft` body `{"title": str, "content": str, "account_id": str}` → `{"media_id": str}`
  - 错误码：401（未登录）、400（参数错/凭证未配置）、500（微信 API 失败）

- [x] **Step 1: 编写 push_draft 路由失败测试**

在 `tests/test_agent_routes.py` 追加：

```python
class TestAgentPushDraftRoute:
    def _auth_session(self, app):
        with app.session_transaction() as sess:
            sess["user"] = {"id": 1, "username": "admin"}
        return app

    def test_push_requires_login(self, app):
        resp = app.post("/api/agent/push_draft",
                        data=json.dumps({"title": "t", "content": "c", "account_id": "demo"}),
                        content_type="application/json")
        assert resp.status_code == 401

    def test_push_missing_title(self, app, tmp_coze_config):
        app = self._auth_session(app)
        resp = app.post("/api/agent/push_draft",
                        data=json.dumps({"title": "", "content": "c", "account_id": "demo"}),
                        content_type="application/json")
        assert resp.status_code == 400

    def test_push_success(self, app, tmp_coze_config, monkeypatch):
        app = self._auth_session(app)
        # mock wx_publisher.WeChatPublisher
        mock_publisher = MagicMock()
        mock_publisher.create_draft_only.return_value = {
            "success": True, "media_id": "mid-123", "msg": "ok",
        }
        monkeypatch.setattr("web_app.WeChatPublisher", lambda *a, **k: mock_publisher)
        monkeypatch.setattr(
            "web_app.get_account_config",
            lambda *a, **k: {"app_id": "aid", "app_secret": "sec", "author": "作者"},
        )

        resp = app.post("/api/agent/push_draft",
                        data=json.dumps({"title": "标题", "content": "正文", "account_id": "demo"}),
                        content_type="application/json")
        assert resp.status_code == 200
        assert resp.get_json()["media_id"] == "mid-123"

    def test_push_wx_error_returns_500(self, app, tmp_coze_config, monkeypatch):
        app = self._auth_session(app)
        from modules.wx_publisher import WeChatAPIError
        mock_publisher = MagicMock()
        mock_publisher.create_draft_only.side_effect = WeChatAPIError("wx boom")
        monkeypatch.setattr("web_app.WeChatPublisher", lambda *a, **k: mock_publisher)
        monkeypatch.setattr("web_app.get_account_config",
                            lambda *a, **k: {"app_id": "aid", "app_secret": "sec"})

        resp = app.post("/api/agent/push_draft",
                        data=json.dumps({"title": "t", "content": "c", "account_id": "demo"}),
                        content_type="application/json")
        assert resp.status_code == 500
```

- [x] **Step 2: 运行测试确认失败**

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python -m pytest tests/test_agent_routes.py::TestAgentPushDraftRoute -v`
Expected: FAIL（路由未定义）

- [x] **Step 3: 在 web_app.py 新增 `/api/agent/push_draft` 路由**

在 `api_agent_generate` 之后追加：

```python
@app.route("/api/agent/push_draft", methods=["POST"])
def api_agent_push_draft():
    """将改写结果推送到公众号草稿箱"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.json or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    account_id = (data.get("account_id") or "").strip()

    if not title:
        return jsonify({"error": "标题不能为空"}), 400
    if not content:
        return jsonify({"error": "正文不能为空"}), 400
    if not account_id:
        return jsonify({"error": "请选择账号"}), 400

    acc_cfg = get_account_config(account_id)
    if not acc_cfg or not acc_cfg.get("app_id") or not acc_cfg.get("app_secret"):
        return jsonify({"error": "账号未配置 AppID/AppSecret"}), 400

    try:
        from modules.wx_publisher import WeChatPublisher
        from modules.md_converter import markdown_to_wechat_html

        # Coze 输出为 Markdown，转为微信草稿所需的 HTML
        content_html = markdown_to_wechat_html(
            content, title=title, author=acc_cfg.get("author", "")
        )

        publisher = WeChatPublisher(
            app_id=acc_cfg["app_id"], app_secret=acc_cfg["app_secret"]
        )
        result = publisher.create_draft_only(
            title=title,
            content_html=content_html,
            author=acc_cfg.get("author", ""),
        )
        return jsonify({"media_id": result["media_id"]})
    except Exception as e:
        return jsonify({"error": f"推送失败：{e}"}), 500
```

> **实现提示**：此处假设 Coze 输出 `content` 为 Markdown 格式，使用现有 `markdown_to_wechat_html` 转换。若 Coze 实际返回 HTML，则去掉转换直接使用 `content`。

- [x] **Step 4: 运行测试确认通过**

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python -m pytest tests/test_agent_routes.py::TestAgentPushDraftRoute -v`
Expected: 全部 PASS

- [x] **Step 5: 提交**

```bash
git add web_app.py tests/test_agent_routes.py
git commit -m "feat: 新增 POST /api/agent/push_draft 路由"
```

---

## Task 5: `agent.html` 页面结构

**Files:**
- Create: `web_static/agent.html`

**Interfaces:**
- Consumes: `loadAccounts()`（common.js）、`/api/agent/generate`、`/api/agent/push_draft`
- Produces: 页面 DOM 结构（供 agent.js 绑定事件）

- [x] **Step 1: 新建 `web_static/agent.html`**

参照 `write.html` 布局，左侧输入区 + 右侧结果区。完整内容：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>智能体 · 墨锻工坊</title>
<link rel="stylesheet" href="/common.css">
<link rel="stylesheet" href="/web_static/agent.css">
</head>
<body>

<div class="layout">
  <!-- 侧边栏 -->
  <aside class="sidebar">
    <div class="sidebar-logo">
      <div class="logo-icon">📱</div>
      <h1>墨锻工坊</h1>
      <p>WeChat Publisher</p>
    </div>
    <nav class="nav">
      <a href="/dashboard.html" class="nav-item"><span class="icon">🏠</span> 工作台</a>
      <a href="/topics.html" class="nav-item"><span class="icon">🔍</span> 自动选题</a>
      <a href="/write.html" class="nav-item"><span class="icon">✍️</span> 写稿 &amp; 预览</a>
      <a href="/rewrite.html" class="nav-item"><span class="icon">🔄</span> 链接改写</a>
      <a href="/import.html" class="nav-item"><span class="icon">📋</span> 一键排版</a>
      <a href="/history.html" class="nav-item"><span class="icon">📂</span> 历史文章</a>
      <a href="/schedule.html" class="nav-item"><span class="icon">⏰</span> 定时任务</a>
      <a href="/config.html" class="nav-item"><span class="icon">⚙️</span> 系统配置</a>
      <a href="/profile.html" class="nav-item"><span class="icon">👤</span> 个人中心</a>
      <a href="/agent.html" class="nav-item"><span class="icon">🤖</span> 智能体</a>
    </nav>
    <div class="sidebar-footer">v1.0 · 公众号自动发布平台</div>
  </aside>

  <!-- 主区域 -->
  <div class="main">
    <div class="topbar">
      <div class="topbar-title">🤖 智能体</div>
      <div class="topbar-actions">
        <select class="form-select" id="account-selector" onchange="onAccountChange()" style="margin-right:12px;min-width:180px;">
          <option value="">-- 加载中 --</option>
        </select>
        <span id="status-dot" class="dot dot-green"></span>
        <span id="status-text" style="font-size:12px;color:var(--text2)">就绪</span>
        <div class="user-menu" id="user-menu" onclick="toggleUserMenu()">
          <div class="user-avatar" id="user-avatar">U</div>
          <div class="user-name" id="user-name">用户</div>
          <div class="user-dropdown" id="user-dropdown">
            <div class="user-dropdown-item" onclick="showUserProfile()"><span>👤</span> 个人中心</div>
            <div class="user-dropdown-divider"></div>
            <div class="user-dropdown-item" onclick="doLogout()"><span>🚪</span> 退出登录</div>
          </div>
        </div>
      </div>
    </div>

    <div class="content">
      <div class="agent-layout">
        <!-- 左侧输入区 -->
        <div class="agent-input-panel">
          <div class="card">
            <div class="card-title">🔗 输入文章链接</div>
            <div class="form-group form-full">
              <label class="form-label">文章链接</label>
              <input class="form-input" id="agent-url" type="text" placeholder="粘贴文章链接，例如：https://www.36kr.com/p/...">
            </div>
            <div class="form-group form-full">
              <label class="form-label">改写提示词</label>
              <textarea class="form-textarea" id="agent-prompt" rows="3" placeholder="描述改写要求...">不要抄袭,去除AI味</textarea>
              <div class="form-hint">提示：可指定风格、角度、受众等。</div>
            </div>
            <button class="btn btn-primary" id="agent-generate-btn" onclick="generateArticle()" style="width:100%;">
              ✨ 生成文章
            </button>
          </div>

          <!-- 生成进度 -->
          <div class="card" id="agent-log-card" style="display:none;margin-top:14px;">
            <div class="card-title">⏳ 生成进度</div>
            <div class="progress-bar"><div class="progress-fill running" id="agent-progress"></div></div>
            <div class="log-terminal" id="agent-log" style="max-height:200px;"></div>
          </div>
        </div>

        <!-- 右侧结果区 -->
        <div class="agent-result-panel">
          <div class="card" id="agent-result-card" style="display:none;">
            <div class="card-title" style="display:flex;align-items:center;justify-content:space-between;">
              <span>✅ 改写结果</span>
              <button class="btn btn-sm btn-primary" id="agent-push-btn" onclick="pushToDraft()">📤 推送到草稿箱</button>
            </div>
            <div class="form-group form-full">
              <label class="form-label">标题</label>
              <input class="form-input" id="agent-result-title" type="text">
            </div>
            <div class="form-group form-full">
              <label class="form-label">正文（Markdown）</label>
              <textarea class="form-textarea" id="agent-result-content" rows="20" style="font-family:inherit;font-size:13px;"></textarea>
            </div>
          </div>

          <!-- 推送结果提示 -->
          <div class="card" id="agent-push-result" style="display:none;margin-top:14px;">
            <div class="card-title">📡 推送结果</div>
            <div id="agent-push-msg" style="font-size:13px;color:var(--text2);"></div>
          </div>
        </div>
      </div>
    </div> <!-- /content -->
  </div> <!-- /main -->
</div> <!-- /layout -->

<script src="/common.js"></script>
<script src="/web_static/agent.js"></script>

<!-- 通知 -->
<div class="toast" id="toast"></div>

</body>
</html>
```

- [x] **Step 2: 提交**

```bash
git add web_static/agent.html
git commit -m "feat: 新增 agent.html 智能体页面结构"
```

---

## Task 6: `agent.js` 交互逻辑

**Files:**
- Create: `web_static/agent.js`

**Interfaces:**
- Consumes: `agent.html` DOM、`toast()`/`setStatus()`（common.js）、`/api/agent/generate`、`/api/agent/push_draft`
- Produces: `generateArticle()`、`pushToDraft()` 全局函数

- [x] **Step 1: 新建 `web_static/agent.js`**

```javascript
// 智能体页面交互逻辑

// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
  // 高亮当前导航项
  const currentPage = window.location.pathname;
  document.querySelectorAll(".nav-item").forEach(item => {
    if (item.getAttribute("href") === currentPage) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  loadAccounts();
});

// 生成文章
async function generateArticle() {
  const url = document.getElementById('agent-url').value.trim();
  const prompt = document.getElementById('agent-prompt').value.trim();
  const accountId = document.getElementById('account-selector').value;

  // 前端校验
  if (!url) {
    toast('请输入文章链接', 'error');
    return;
  }
  if (!accountId) {
    toast('请选择账号', 'error');
    return;
  }

  const btn = document.getElementById('agent-generate-btn');
  btn.disabled = true;
  btn.textContent = '⏳ 生成中，请稍候...';
  setStatus('正在生成...', 'dot-yellow');

  // 显示进度区
  const logCard = document.getElementById('agent-log-card');
  const logEl = document.getElementById('agent-log');
  logCard.style.display = 'block';
  logEl.innerHTML = '';
  document.getElementById('agent-result-card').style.display = 'none';
  document.getElementById('agent-push-result').style.display = 'none';

  try {
    const res = await fetch('/api/agent/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, account_id: accountId, prompt }),
    });
    const data = await res.json();

    if (res.status === 401) {
      toast('请先登录', 'error');
      setTimeout(() => { window.location.href = '/login.html'; }, 1000);
      return;
    }
    if (res.status === 400) {
      toast(data.error || '参数错误', 'error');
      return;
    }
    if (res.status === 502 || res.status === 504) {
      toast(data.error || '生成失败，请重试', 'error');
      return;
    }
    if (!data.title && !data.content) {
      toast('生成失败：返回结果为空', 'error');
      return;
    }

    // 展示结果
    document.getElementById('agent-result-title').value = data.title || '';
    document.getElementById('agent-result-content').value = data.content || '';
    document.getElementById('agent-result-card').style.display = 'block';
    toast('文章生成成功！', 'success');
    setStatus('生成完成', 'dot-green');
  } catch (err) {
    toast('生成失败：' + err.message, 'error');
    setStatus('生成失败', 'dot-red');
  } finally {
    btn.disabled = false;
    btn.textContent = '✨ 生成文章';
    logCard.style.display = 'none';
  }
}

// 推送到草稿箱
async function pushToDraft() {
  const title = document.getElementById('agent-result-title').value.trim();
  const content = document.getElementById('agent-result-content').value.trim();
  const accountId = document.getElementById('account-selector').value;

  if (!title) {
    toast('标题不能为空', 'error');
    return;
  }
  if (!content) {
    toast('正文不能为空', 'error');
    return;
  }
  if (!accountId) {
    toast('请选择账号', 'error');
    return;
  }

  const btn = document.getElementById('agent-push-btn');
  btn.disabled = true;
  btn.textContent = '⏳ 推送中...';
  setStatus('推送中...', 'dot-yellow');

  try {
    const res = await fetch('/api/agent/push_draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content, account_id: accountId }),
    });
    const data = await res.json();

    const resultCard = document.getElementById('agent-push-result');
    const msgEl = document.getElementById('agent-push-msg');
    resultCard.style.display = 'block';

    if (res.status === 401) {
      toast('请先登录', 'error');
      msgEl.textContent = '未登录，请重新登录';
      return;
    }
    if (res.status === 400) {
      toast(data.error || '参数错误', 'error');
      msgEl.textContent = data.error || '参数错误';
      return;
    }
    if (res.status === 500) {
      toast('推送失败：' + (data.error || '微信 API 错误'), 'error');
      msgEl.textContent = '推送失败：' + (data.error || '微信 API 错误') + '。内容已保留，可修改后重试。';
      return;
    }
    if (!data.media_id) {
      toast('推送失败：未返回 media_id', 'error');
      return;
    }

    msgEl.innerHTML = `✅ 草稿创建成功！media_id：<code>${data.media_id}</code><br>请登录公众号后台审核后发布。`;
    toast('已推送到草稿箱！', 'success');
    setStatus('推送成功', 'dot-green');
  } catch (err) {
    toast('推送失败：' + err.message, 'error');
    setStatus('推送失败', 'dot-red');
  } finally {
    btn.disabled = false;
    btn.textContent = '📤 推送到草稿箱';
  }
}
```

- [x] **Step 2: 提交**

```bash
git add web_static/agent.js
git commit -m "feat: 新增 agent.js 交互逻辑（生成 + 推草稿）"
```

---

## Task 7: `agent.css` 页面样式

**Files:**
- Create: `web_static/agent.css`

**Interfaces:**
- Consumes: `agent.html` 的 class 与结构
- Produces: 智能体页面专属样式（输入/结果双栏布局）

- [x] **Step 1: 新建 `web_static/agent.css`**

```css
/* 智能体页面样式 */

.agent-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.agent-input-panel {
  width: 380px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.agent-result-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* 响应式：窄屏改为上下堆叠 */
@media (max-width: 900px) {
  .agent-layout {
    flex-direction: column;
  }
  .agent-input-panel {
    width: 100%;
  }
}

/* 结果区 textarea 高度自适应 */
#agent-result-content {
  min-height: 400px;
  resize: vertical;
  line-height: 1.7;
}
```

- [x] **Step 2: 提交**

```bash
git add web_static/agent.css
git commit -m "feat: 新增 agent.css 智能体页面样式"
```

---

## Task 8: 侧边栏集成 + agent.html 页面路由

**Files:**
- Modify: `web_app.py`
- Modify: `web_static/dashboard.html`
- Modify: `web_static/topics.html`
- Modify: `web_static/write.html`
- Modify: `web_static/rewrite.html`
- Modify: `web_static/import.html`
- Modify: `web_static/history.html`
- Modify: `web_static/schedule.html`
- Modify: `web_static/config.html`
- Modify: `web_static/profile.html`

**Interfaces:**
- Consumes: 现有侧边栏 `<nav class="nav">` 结构
- Produces: 所有页面侧边栏新增「智能体」菜单项；`/agent.html` 页面路由

- [x] **Step 1: 在 web_app.py 新增 `/agent.html` 页面路由**

在 `profile` 路由之后追加：

```python
@app.route("/agent.html")
def agent_page():
    """智能体页面"""
    session_id = _get_session_id()
    user = get_current_user(session_id)
    if not user:
        return redirect("/login.html")
    return send_from_directory(str(BASE_DIR / "web_static"), "agent.html")
```

- [x] **Step 2: 在全部 9 个页面侧边栏新增「智能体」菜单项**

对以下 9 个文件（dashboard、topics、write、rewrite、import、history、schedule、config、profile），在 `<nav class="nav">` 内最后一个 `</a>`（个人中心）之后、`</nav>` 之前，追加：

```html
      <a href="/agent.html" class="nav-item">
        <span class="icon">🤖</span> 智能体
      </a>
```

> **注意**：`agent.html` 自身已在 Task 5 中直接包含该菜单项，无需再次修改。

- [x] **Step 3: 验证激活态逻辑无需额外修改**

确认每个页面的 `DOMContentLoaded` 中已有以下逻辑（现有页面均已具备）：

```javascript
const currentPage = window.location.pathname;
document.querySelectorAll(".nav-item").forEach(item => {
  if (item.getAttribute("href") === currentPage) {
    item.classList.add("active");
  } else {
    item.classList.remove("active");
  }
});
```

当 `currentPage === "/agent.html"` 时，`href="/agent.html"` 的菜单项会自动高亮。**无需额外代码**。

- [x] **Step 4: 本地启动验证侧边栏**

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python web_app.py &`
手动检查：浏览器访问 `http://localhost:5678/agent.html`，确认：
1. 侧边栏显示「🤖 智能体」菜单项
2. 当前「智能体」项高亮（active）
3. 其他页面侧边栏也包含该菜单项且点击可跳转

按 Ctrl+C 停止服务。

- [x] **Step 5: 提交**

```bash
git add web_app.py web_static/dashboard.html web_static/topics.html web_static/write.html web_static/rewrite.html web_static/import.html web_static/history.html web_static/schedule.html web_static/config.html web_static/profile.html
git commit -m "feat: 侧边栏新增智能体菜单项 + agent.html 页面路由"
```

---

## Task 9: 端到端验证与异常场景

**Files:**
- 无新增文件（验证任务）

**Interfaces:**
- Consumes: 全部已实现的模块与路由
- Produces: 完整流程跑通确认 + 异常场景确认

- [x] **Step 1: 完整流程验证（需真实 Coze 配置）**

前置条件：在 `config.html` → Coze 工作流配置中填入有效的 Workflow ID 与 API Token 并保存。

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python web_app.py &`

手动执行：
1. 浏览器访问 `http://localhost:5678/agent.html`
2. 选择账号（使用已配置 AppID/AppSecret 的账号）
3. 输入一篇真实文章链接
4. 点击「✨ 生成文章」
5. 等待生成完成，确认右侧展示标题和正文
6. 点击「📤 推送到草稿箱」
7. 确认返回 media_id，提示成功
8. 登录公众号后台确认草稿存在

按 Ctrl+C 停止服务。

- [x] **Step 2: 异常场景验证**

逐项验证，确认均有友好提示且不崩溃：

| 场景 | 操作 | 预期结果 |
|------|------|----------|
| 空链接提交 | 不填链接直接点生成 | toast「请输入文章链接」 |
| 未选账号 | 不选账号点生成 | toast「请选择账号」 |
| Coze 未配置 | 清空 coze_config 后刷新页面点生成 | 提示「请先配置 Coze 工作流」 |
| Coze 超时/错误 | （可通过临时改错 token 模拟） | 提示「生成失败」 |
| 推送失败 | （可通过临时改错 AppSecret 模拟） | 显示微信 API 错误原因，内容保留 |

- [x] **Step 3: 运行全量测试确认无回归**

Run: `cd /Users/casey/workspace/wechat-publisher/.worktrees/coze-agent && python -m pytest tests/ -v`
Expected: 全部 PASS

- [x] **Step 4: 最终提交（若有配置微调）**

```bash
git add -A
git commit -m "feat: 智能体模块端到端验证完成" || echo "无待提交变更"
```

---

## 实施顺序建议

按任务编号顺序实施（1 → 9），依赖关系如下：

```
Task 1 (coze_client) ─┐
                       ├→ Task 3 (generate) ─┐
Task 2 (coze_config) ──┘                      ├→ Task 5/6/7 (前端) ─→ Task 8 (侧边栏) ─→ Task 9 (E2E)
                       Task 4 (push_draft) ───┘
```

Task 1 与 Task 2 可并行；Task 3 与 Task 4 可并行；Task 5/6/7 可并行。

## 风险与注意事项

1. **Coze 输出字段名**：`result.data` 中 title/content 的精确 key 需从 Coze 实际返回确认，实现 Task 1 时若字段名不同仅改 `rewrite_article` 中的 `output.get(key)`。
2. **Coze 输出格式**：Task 4 假设 `content` 为 Markdown；若实际为 HTML，需去掉 `markdown_to_wechat_html` 转换。
3. **同步调用超时**：`/api/agent/generate` 为同步调用（设计文档约定），Coze 60s 超时由 `SyncHTTPClient(timeout=60)` 控制。若实际耗时超 60s，前端会收到 502，后续可升级为 SSE 流式。
4. **侧边栏逐页复制**：共需修改 9 个页面 + agent.html 自身，实现时逐页检查避免遗漏。
