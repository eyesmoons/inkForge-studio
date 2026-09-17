"""
modules/ai_assistant.py
AI 助手模块 - 集成 DeepSeek API

功能：
- 辅助写作
- 文章润色
- 内容扩写/缩写
- 标题生成
- 选题建议
"""

import os
import json
import requests
from typing import List, Dict, Optional, Generator
from datetime import datetime

# DeepSeek API 配置（默认从环境变量，会被数据库配置覆盖）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def get_ai_config_from_db(user_id: int = None) -> Dict:
    """
    从数据库获取 AI 模型配置
    优先返回默认模型配置
    """
    try:
        from modules.user_db import UserDB
        
        with UserDB() as db:
            # 先尝试获取默认模型
            model = db.get_user_default_ai_model(user_id)
            
            # 如果没有默认模型，获取所有模型中的第一个
            if not model:
                models = db.get_user_ai_models(user_id)
                if models:
                    model = models[0]
            
            if model:
                return {
                    "api_key": model.get("api_key", ""),
                    "api_base": model.get("api_base", ""),
                    "model_name": model.get("model_name", "deepseek-chat"),
                    "provider": model.get("provider", "deepseek"),
                }
    except Exception as e:
        print(f"[AI助手] 读取数据库配置失败: {e}")
    
    return {}


def get_api_key(user_id: int = None) -> str:
    """获取 API Key，优先从数据库读取"""
    # 1. 尝试从数据库读取
    db_config = get_ai_config_from_db(user_id)
    if db_config.get("api_key"):
        return db_config["api_key"]
    
    # 2. 回退到环境变量
    return os.environ.get("DEEPSEEK_API_KEY", "")


def get_api_base(user_id: int = None) -> str:
    """获取 API Base URL"""
    db_config = get_ai_config_from_db(user_id)
    if db_config.get("api_base"):
        return db_config["api_base"]
    return "https://api.deepseek.com"


def get_model_name(user_id: int = None) -> str:
    """获取模型名称"""
    db_config = get_ai_config_from_db(user_id)
    if db_config.get("model_name"):
        return db_config["model_name"]
    return "deepseek-chat"

# 预设提示词模板
PROMPT_TEMPLATES = {
    "writing": """你是一位资深编辑，擅长撰写通俗易懂、有深度的文章。
请根据以下要求写作：
- 风格：通俗易懂，避免过于学术化
- 结构：有清晰的开头、主体、结尾
- 语言：流畅自然，适合大众阅读

用户请求：{input}""",

    "polish": """你是一位专业的文字编辑，请对以下文章进行润色优化：
- 修正语法错误和不通顺的表达
- 优化段落结构，增强逻辑性
- 提升文字的感染力和可读性
- 保持原文的核心观点和事实准确

原文：
{input}""",

    "expand": """请对以下内容进行扩写，使其更加详细和丰富：
- 补充背景信息和细节
- 增加案例或数据支撑
- 扩展论述的深度和广度
- 保持语言风格一致

原文：
{input}""",

    "condense": """请对以下内容进行精简缩写：
- 保留核心观点和关键信息
- 删除冗余描述和重复内容
- 使表达更加简洁有力
- 保持逻辑完整

原文：
{input}""",

    "title": None,  # 动态构建，统一使用 title_generator.TITLE_GEN_PROMPT

    "topic": """你是一位内容策划专家，请针对以下领域提供选题建议：
要求：
- 结合当前热点趋势
- 有独特视角和深度
- 适合传播
- 提供简要的内容大纲

领域/关键词：{input}""",
}


def chat(
    messages: List[Dict[str, str]],
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    user_id: int = None,
) -> Dict:
    """
    调用 DeepSeek API 进行对话
    
    Args:
        messages: 消息列表，格式 [{"role": "user"/"assistant"/"system", "content": "..."}]
        stream: 是否流式返回
        temperature: 创造性参数 (0-1)
        max_tokens: 最大生成token数
        user_id: 用户ID，用于读取数据库配置
    
    Returns:
        {"ok": True, "content": "...", "usage": {...}} 或 {"ok": False, "error": "..."}
    """
    api_key = get_api_key(user_id)
    if not api_key:
        return {"ok": False, "error": "未配置 AI API Key，请在系统配置的 AI 模型管理中配置"}
    
    api_base = get_api_base(user_id)
    model_name = get_model_name(user_id)
    api_url = f"{api_base}/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    
    try:
        resp = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=60,
        )
        
        # 检查HTTP错误
        if resp.status_code != 200:
            error_msg = f"API 请求失败 (HTTP {resp.status_code})"
            try:
                error_data = resp.json()
                if "error" in error_data:
                    error_msg = f"API 错误: {error_data['error'].get('message', error_data['error'])}"
            except:
                error_msg = f"API 请求失败: {resp.text[:200]}"
            return {"ok": False, "error": error_msg}
        
        data = resp.json()
        
        if stream:
            return {"ok": True, "stream": True, "data": data}
        
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        
        return {
            "ok": True,
            "content": content,
            "usage": usage,
        }
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"API 请求失败: {str(e)}"}
    except Exception as e:
        return {"ok": False, "error": f"处理失败: {str(e)}"}


def chat_stream(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    user_id: int = None,
) -> Generator[str, None, None]:
    """
    流式调用 DeepSeek API
    
    Yields:
        生成的文本片段
    """
    api_key = get_api_key(user_id)
    if not api_key:
        yield json.dumps({"error": "未配置 AI API Key，请在系统配置的 AI 模型管理中配置"})
        return
    
    api_base = get_api_base(user_id)
    model_name = get_model_name(user_id)
    api_url = f"{api_base}/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    
    try:
        resp = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=60,
            stream=True,
        )
        resp.raise_for_status()
        
        for line in resp.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield json.dumps({"error": str(e)})


def quick_chat(user_input: str, mode: str = "chat", history: List[Dict] = None, user_id: int = None) -> Dict:
    """
    快速对话接口
    
    Args:
        user_input: 用户输入
        mode: 模式 - chat/writing/polish/expand/condense/title/topic
        history: 历史对话记录
        user_id: 用户ID，用于读取数据库配置
    
    Returns:
        {"ok": True, "content": "..."} 或 {"ok": False, "error": "..."}
    """
    messages = history or []
    
    if mode in PROMPT_TEMPLATES:
        template = PROMPT_TEMPLATES[mode]
        if template is None:
            # title 模式动态构建，统一使用 title_generator 的提示词
            from modules.title_generator import TITLE_GEN_PROMPT
            prompt = f"""{TITLE_GEN_PROMPT}

## 文章内容

{user_input}

## 要求
- 请生成 5 个标题，风格各异，覆盖不同的爆款特征
- 每个标题一行，用序号 1-5 标注，不要额外解释
"""
        else:
            prompt = template.format(input=user_input)
        messages.append({"role": "user", "content": prompt})
    else:
        # 普通对话模式
        messages.append({"role": "user", "content": user_input})
    
    return chat(messages, user_id=user_id)


# 对话历史管理（简单内存存储，后续可扩展为数据库存储）
_chat_histories: Dict[str, List[Dict]] = {}


def get_chat_history(session_id: str) -> List[Dict]:
    """获取对话历史"""
    return _chat_histories.get(session_id, [])


def add_to_history(session_id: str, role: str, content: str):
    """添加消息到历史"""
    if session_id not in _chat_histories:
        _chat_histories[session_id] = []
    
    _chat_histories[session_id].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    })
    
    # 只保留最近 20 轮对话
    if len(_chat_histories[session_id]) > 40:
        _chat_histories[session_id] = _chat_histories[session_id][-40:]


def clear_history(session_id: str):
    """清空对话历史"""
    _chat_histories.pop(session_id, None)
