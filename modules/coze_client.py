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
