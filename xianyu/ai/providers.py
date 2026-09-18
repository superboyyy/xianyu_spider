"""多厂商 LLM 适配：OpenAI 兼容、Anthropic、Azure、Ollama。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from xianyu.secrets import get_key, load_settings

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "protocol": "openai",
        "needs_key": True,
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "protocol": "openai",
        "needs_key": True,
    },
    "ollama": {
        "label": "Ollama 本地",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "llama3.1",
        "protocol": "openai",
        "needs_key": False,
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-5",
        "protocol": "anthropic",
        "needs_key": True,
    },
    "azure": {
        "label": "Azure OpenAI",
        "base_url": "",
        "model": "gpt-4o-mini",
        "protocol": "azure",
        "needs_key": True,
        "hint": "Base URL 填 https://{resource}.openai.azure.com，Model 填部署名",
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
        "protocol": "openai",
        "needs_key": True,
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "protocol": "openai",
        "needs_key": True,
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
        "protocol": "openai",
        "needs_key": True,
    },
    "qwen": {
        "label": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "protocol": "openai",
        "needs_key": True,
    },
    "moonshot": {
        "label": "月之暗面 Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-auto",
        "protocol": "openai",
        "needs_key": True,
    },
    "zhipu": {
        "label": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "protocol": "openai",
        "needs_key": True,
    },
    "siliconflow": {
        "label": "硅基流动",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3",
        "protocol": "openai",
        "needs_key": True,
    },
    "together": {
        "label": "Together",
        "base_url": "https://api.together.xyz/v1",
        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "protocol": "openai",
        "needs_key": True,
    },
    "minimax": {
        "label": "MiniMax",
        "base_url": "https://api.minimax.chat/v1",
        "model": "MiniMax-Text-01",
        "protocol": "openai",
        "needs_key": True,
    },
    "yi": {
        "label": "零一万物",
        "base_url": "https://api.lingyiwanwu.com/v1",
        "model": "yi-lightning",
        "protocol": "openai",
        "needs_key": True,
    },
    "custom": {
        "label": "自定义 OpenAI 兼容",
        "base_url": "",
        "model": "",
        "protocol": "openai",
        "needs_key": True,
        "hint": "任意 /v1/chat/completions 端点",
    },
}

_HOST_HINTS = (
    ("api.openai.com", "openai"),
    ("deepseek.com", "deepseek"),
    (":11434", "ollama"),
    ("ollama", "ollama"),
    ("api.anthropic.com", "anthropic"),
    ("openai.azure.com", "azure"),
    ("generativelanguage.googleapis.com", "gemini"),
    ("api.groq.com", "groq"),
    ("openrouter.ai", "openrouter"),
    ("dashscope.aliyuncs.com", "qwen"),
    ("moonshot.cn", "moonshot"),
    ("bigmodel.cn", "zhipu"),
    ("siliconflow.cn", "siliconflow"),
    ("together.xyz", "together"),
    ("minimax.chat", "minimax"),
    ("lingyiwanwu.com", "yi"),
)


def detect_provider_id(base_url: str) -> str:
    text = (base_url or "").strip().lower()
    if not text:
        return "deepseek"
    for needle, provider_id in _HOST_HINTS:
        if needle in text:
            return provider_id
    host = urlparse(text if "://" in text else f"https://{text}").hostname or ""
    if host in {"127.0.0.1", "localhost"}:
        return "ollama"
    return "custom"


def list_providers() -> list[dict[str, Any]]:
    items = []
    for provider_id, preset in PROVIDER_PRESETS.items():
        items.append(
            {
                "id": provider_id,
                "label": preset["label"],
                "base_url": preset["base_url"],
                "model": preset["model"],
                "protocol": preset["protocol"],
                "needs_key": bool(preset.get("needs_key", True)),
                "hint": preset.get("hint") or "",
            }
        )
    return items


@dataclass(frozen=True)
class LLMConfig:
    provider_id: str
    label: str
    protocol: str
    base_url: str
    model: str
    api_key: str
    needs_key: bool
    api_version: str = "2024-06-01"

    @property
    def can_call(self) -> bool:
        if not self.base_url or not self.model:
            return False
        return bool(self.api_key) or not self.needs_key


def resolve_config(
    settings: dict[str, Any] | None = None,
    *,
    env: dict[str, str] | None = None,
) -> LLMConfig:
    data = dict(settings or load_settings())
    environ = env if env is not None else os.environ
    requested = str(data.get("ai_provider") or environ.get("AI_PROVIDER") or "auto").strip().lower()
    base = (
        data.get("ai_base_url") or environ.get("AI_BASE_URL") or ""
    ).strip().rstrip("/")
    model = str(data.get("ai_model") or environ.get("AI_MODEL") or "").strip()
    key = (
        get_key("ai_api_key")
        or environ.get("AI_API_KEY")
        or environ.get("OPENAI_API_KEY")
        or environ.get("ANTHROPIC_API_KEY")
        or environ.get("GEMINI_API_KEY")
        or ""
    )
    if requested in {"", "auto"}:
        provider_id = detect_provider_id(base) if base else "deepseek"
    elif requested in PROVIDER_PRESETS:
        provider_id = requested
    else:
        provider_id = "custom"
    preset = PROVIDER_PRESETS[provider_id]
    if not base:
        base = str(preset.get("base_url") or "").rstrip("/")
    if not model:
        model = str(preset.get("model") or "")
    return LLMConfig(
        provider_id=provider_id,
        label=str(preset.get("label") or provider_id),
        protocol=str(preset.get("protocol") or "openai"),
        base_url=base,
        model=model,
        api_key=str(key or ""),
        needs_key=bool(preset.get("needs_key", True)),
        api_version=str(environ.get("AZURE_OPENAI_API_VERSION") or "2024-06-01"),
    )


def openai_headers(cfg: LLMConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if cfg.protocol == "azure":
        if cfg.api_key:
            headers["api-key"] = cfg.api_key
        return headers
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    elif cfg.provider_id == "ollama":
        headers["Authorization"] = "Bearer ollama"
    return headers


def openai_chat_url(cfg: LLMConfig) -> str:
    base = cfg.base_url.rstrip("/")
    if cfg.protocol == "azure":
        return f"{base}/openai/deployments/{cfg.model}/chat/completions?api-version={cfg.api_version}"
    if not base.endswith("/v1") and not base.endswith("/v4") and "/compatible-mode/" not in base:
        if base.endswith("/openai"):
            return f"{base}/chat/completions"
    return f"{base}/chat/completions"


def anthropic_url(cfg: LLMConfig) -> str:
    base = cfg.base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def anthropic_headers(cfg: LLMConfig) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-api-key": cfg.api_key,
        "anthropic-version": "2023-06-01",
    }


def openai_tools_to_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for tool in tools:
        fn = tool.get("function") or tool
        converted.append(
            {
                "name": fn.get("name"),
                "description": fn.get("description") or "",
                "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return converted


def openai_messages_to_anthropic(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role == "system":
            system_parts.append(str(message.get("content") or ""))
            continue
        if role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.get("tool_call_id") or "",
                            "content": str(message.get("content") or ""),
                        }
                    ],
                }
            )
            continue
        if role == "assistant" and message.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            text = str(message.get("content") or "").strip()
            if text:
                blocks.append({"type": "text", "text": text})
            for call in message.get("tool_calls") or []:
                fn = call.get("function") or {}
                raw_args = fn.get("arguments") or "{}"
                if isinstance(raw_args, str):
                    import json

                    try:
                        args = json.loads(raw_args)
                    except Exception:
                        args = {}
                else:
                    args = raw_args
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.get("id") or "",
                        "name": fn.get("name") or "",
                        "input": args if isinstance(args, dict) else {},
                    }
                )
            out.append({"role": "assistant", "content": blocks})
            continue
        out.append({"role": "assistant" if role == "assistant" else "user", "content": message.get("content") or ""})
    return "\n".join(part for part in system_parts if part), out


def anthropic_to_openai_message(data: dict[str, Any]) -> dict[str, Any]:
    content = data.get("content") or []
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    if isinstance(content, str):
        return {"role": "assistant", "content": content, "tool_calls": []}
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text_parts.append(str(block.get("text") or ""))
        elif block.get("type") == "tool_use":
            import json

            tool_calls.append(
                {
                    "id": block.get("id") or "",
                    "type": "function",
                    "function": {
                        "name": block.get("name") or "",
                        "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                    },
                }
            )
    return {
        "role": "assistant",
        "content": "\n".join(part for part in text_parts if part),
        "tool_calls": tool_calls,
    }
