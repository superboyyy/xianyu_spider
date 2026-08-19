"""登录态落盘，避免每次重启都重新贴 Cookie。"""

from __future__ import annotations

import json
from typing import Optional

from xianyu.config import SESSION_PATH


def load_session() -> Optional[dict]:
    if not SESSION_PATH.exists():
        return None
    try:
        return json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_session(payload: dict) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_session() -> None:
    if SESSION_PATH.exists():
        SESSION_PATH.unlink()
