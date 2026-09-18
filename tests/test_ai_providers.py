from xianyu.ai.providers import (
    detect_provider_id,
    list_providers,
    openai_chat_url,
    openai_messages_to_anthropic,
    resolve_config,
)
from xianyu.notify.service import prepare_request
from xianyu.secrets import normalize_autoreply_mode


def test_detect_common_hosts():
    assert detect_provider_id("https://api.deepseek.com/v1") == "deepseek"
    assert detect_provider_id("https://api.openai.com/v1") == "openai"
    assert detect_provider_id("http://127.0.0.1:11434/v1") == "ollama"
    assert detect_provider_id("https://api.anthropic.com") == "anthropic"
    assert detect_provider_id("https://my.openai.azure.com") == "azure"
    assert detect_provider_id("https://dashscope.aliyuncs.com/compatible-mode/v1") == "qwen"
    assert detect_provider_id("https://unknown.example/v1") == "custom"


def test_resolve_ollama_does_not_need_key():
    cfg = resolve_config(
        {"ai_provider": "ollama", "ai_base_url": "", "ai_model": ""},
        env={},
    )
    assert cfg.provider_id == "ollama"
    assert cfg.needs_key is False
    assert cfg.can_call is True
    assert "11434" in cfg.base_url


def test_resolve_openai_needs_key():
    cfg = resolve_config(
        {"ai_provider": "openai", "ai_base_url": "", "ai_model": "gpt-4o-mini"},
        env={},
    )
    assert cfg.needs_key is True
    assert cfg.can_call is False


def test_azure_chat_url():
    cfg = resolve_config(
        {
            "ai_provider": "azure",
            "ai_base_url": "https://demo.openai.azure.com",
            "ai_model": "shop-gpt",
        },
        env={"AZURE_OPENAI_API_VERSION": "2024-06-01", "AI_API_KEY": "abc"},
    )
    assert cfg.protocol == "azure"
    assert "deployments/shop-gpt" in openai_chat_url(cfg)


def test_anthropic_message_convert():
    system, messages = openai_messages_to_anthropic(
        [
            {"role": "system", "content": "助手"},
            {"role": "user", "content": "均价"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "price_stats", "arguments": '{"keyword":"相机"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
        ]
    )
    assert system == "助手"
    assert messages[0]["role"] == "user"
    assert messages[1]["content"][0]["type"] == "tool_use"
    assert messages[2]["content"][0]["type"] == "tool_result"


def test_provider_catalog_covers_major_vendors():
    ids = {item["id"] for item in list_providers()}
    for name in ("openai", "deepseek", "ollama", "anthropic", "gemini", "qwen", "moonshot"):
        assert name in ids


def test_autoreply_send_is_draft():
    assert normalize_autoreply_mode("send") == "draft"
    assert normalize_autoreply_mode("off") == "off"
    assert normalize_autoreply_mode("weird") == "off"


def test_notify_prepare_urls():
    bark = prepare_request("bark", "abc123", "上新", "相机")
    assert bark["method"] == "GET"
    assert "api.day.app/abc123" in bark["url"]

    ntfy = prepare_request("ntfy", "deals", "上新", "相机")
    assert ntfy["url"] == "https://ntfy.sh/deals"
    assert ntfy["headers"]["Title"] == "上新"

    tg = prepare_request("telegram", "123:ABC|999", "上新", "相机")
    assert tg["url"] == "https://api.telegram.org/bot123:ABC/sendMessage"
    assert tg["json"]["chat_id"] == "999"

    sct = prepare_request("serverchan", "SCTKEY", "上新", "相机")
    assert sct["url"] == "https://sctapi.ftqq.com/SCTKEY.send"

    wecom = prepare_request("wecom", "hookkey", "上新", "相机")
    assert "qyapi.weixin.qq.com" in wecom["url"]
    assert wecom["json"]["msgtype"] == "text"
