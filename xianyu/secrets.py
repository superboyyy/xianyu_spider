"""本机密钥与设置：LLM / 自动回复模式等。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xianyu.config import DATA_DIR

KEYS_PATH = DATA_DIR / "keys.json"
SETTINGS_PATH = DATA_DIR / "settings.json"

_DEFAULT_SETTINGS = {
    "autoreply_mode": "off",  # off | draft | send
    "ai_base_url": "",
    "ai_model": "deepseek-chat",
}


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)
    return data if isinstance(data, dict) else dict(default)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except Exception:
        pass


def load_keys() -> dict[str, Any]:
    return _read_json(KEYS_PATH, {})


def save_keys(data: dict[str, Any]) -> dict[str, Any]:
    current = load_keys()
    current.update({k: v for k, v in data.items() if v is not None})
    _write_json(KEYS_PATH, current)
    return {k: ("***" if k.endswith("_key") or k.endswith("token") or "key" in k.lower() else v) for k, v in current.items()}


def get_key(name: str, default: str = "") -> str:
    keys = load_keys()
    value = keys.get(name)
    return str(value) if value else default


def load_settings() -> dict[str, Any]:
    data = _read_json(SETTINGS_PATH, _DEFAULT_SETTINGS)
    merged = dict(_DEFAULT_SETTINGS)
    merged.update(data)
    return merged


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    for key, value in patch.items():
        if key in _DEFAULT_SETTINGS or key.startswith("ai_"):
            current[key] = value
    _write_json(SETTINGS_PATH, current)
    return current


def masked_settings() -> dict[str, Any]:
    settings = load_settings()
    keys = load_keys()
    return {
        **settings,
        "has_ai_api_key": bool(keys.get("ai_api_key") or keys.get("OPENAI_API_KEY")),
        "has_bark": bool(keys.get("bark_key")),
    }
