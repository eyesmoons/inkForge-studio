import json
from unittest.mock import patch
from modules import ai_writer

def _topics_prompt_ok(*args, **kwargs):
    return json.dumps([{"title": "t1", "description": "d1"}, {"title": "t2", "description": "d2"}], ensure_ascii=False)

def _outline_prompt_ok(*args, **kwargs):
    return json.dumps({"sections": [{"id": "s1", "title": "章节", "points": ["p1"], "children": []}]}, ensure_ascii=False)

def _content_prompt_ok(*args, **kwargs):
    return json.dumps({"sections": [{"id": "s1", "title": "章节", "content": "正文", "status": "generated"}]}, ensure_ascii=False)

def test_generate_topics():
    with patch("modules.ai_writer._detect_llm_backend", return_value=("openai", {"api_key":"k","api_base":"https://x","model":"m"})), \
         patch("modules.ai_writer._call_openai", side_effect=_topics_prompt_ok):
        topics = ai_writer.generate_topics("AI 手机", count=2)
    assert isinstance(topics, list) and len(topics) == 2
    assert {"title", "description"} <= set(topics[0])

def test_generate_outline():
    with patch("modules.ai_writer._detect_llm_backend", return_value=("ollama", {"model":"qwen"})), \
         patch("modules.ai_writer._call_ollama", side_effect=_outline_prompt_ok):
        outline = ai_writer.generate_outline("AI 手机")
    assert "sections" in outline and outline["sections"][0]["id"] == "s1"

def test_generate_content_full_and_section():
    with patch("modules.ai_writer._detect_llm_backend", return_value=("openai", {"api_key":"k","api_base":"https://x","model":"m"})), \
         patch("modules.ai_writer._call_openai", side_effect=_content_prompt_ok):
        full = ai_writer.generate_content({"sections": [{"id":"s1","title":"x"}]})
        partial = ai_writer.generate_content({"sections": [{"id":"s1","title":"x"}]}, section="s1")
    assert full["sections"][0]["content"] == "正文"
    assert partial["sections"][0]["id"] == "s1"

def test_fallback_to_template_when_no_llm():
    with patch("modules.ai_writer._detect_llm_backend", return_value=("template", {})):
        topics = ai_writer.generate_topics("AI 手机")
        outline = ai_writer.generate_outline("AI 手机")
        content = ai_writer.generate_content({"sections": [{"id":"s1","title":"x"}]})
    assert isinstance(topics, list) and len(topics) > 0
    assert "sections" in outline
    assert isinstance(content.get("sections"), list)
