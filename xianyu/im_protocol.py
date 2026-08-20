"""闲鱼 IM 推送解码：LWP JSON / Base64 JSON。"""

from __future__ import annotations

import base64
import json
import time
import uuid
from typing import Any, Optional


def generate_mid() -> str:
    return f"{int(time.time() * 1000)}{uuid.uuid4().hex[:8]}"


def generate_uuid() -> str:
    return f"-{int(time.time() * 1000)}{uuid.uuid4().int % 10}"


def _b64decode(data: str) -> bytes:
    padded = data.replace("-", "+").replace("_", "/")
    padded += "=" * ((4 - len(padded) % 4) % 4)
    return base64.b64decode(padded)


def decode_payload(data: Any) -> Any:
    if data is None or isinstance(data, (dict, list, int, float, bool)):
        return data
    if not isinstance(data, str):
        return data
    text = data.strip()
    if not text:
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        raw = _b64decode(text)
    except Exception:
        return data
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        pass
    try:
        import msgpack

        return msgpack.unpackb(raw, raw=False, strict_map_key=False)
    except Exception:
        try:
            return raw.decode("utf-8", errors="ignore")
        except Exception:
            return data


def _lookup(node: Any, key: Any) -> Any:
    if not isinstance(node, dict):
        return None
    if key in node:
        return node[key]
    if isinstance(key, int) and str(key) in node:
        return node[str(key)]
    if isinstance(key, str) and key.isdigit() and int(key) in node:
        return node[int(key)]
    return None


def find_first(node: Any, *names: str) -> Any:
    if isinstance(node, dict):
        for name in names:
            if name in node and node[name] not in (None, ""):
                return node[name]
        for value in node.values():
            found = find_first(value, *names)
            if found not in (None, ""):
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_first(value, *names)
            if found not in (None, ""):
                return found
    return None


def extract_incoming_message(payload: Any) -> Optional[dict[str, str]]:
    decoded = decode_payload(payload)
    if decoded is None or decoded == "":
        return None

    if isinstance(decoded, str):
        text = decoded.strip()
        if not text:
            return None
        return {
            "conversation_id": "",
            "sender_id": "",
            "sender_name": "",
            "text": text,
        }

    reminder = find_first(decoded, "reminderContent", "reminder_content")
    title = find_first(decoded, "reminderTitle", "reminder_title")
    sender = find_first(decoded, "senderUserId", "sender_user_id", "senderId")
    cid = find_first(decoded, "cid", "conversationId", "conversation_id")

    numbered = _lookup(decoded, 1) or _lookup(decoded, "1")
    if isinstance(numbered, dict):
        cid = cid or _lookup(numbered, 2) or _lookup(numbered, "2")
        ext = _lookup(numbered, 10) or _lookup(numbered, "10")
        if isinstance(ext, dict):
            title = title or ext.get("reminderTitle") or ext.get("reminder_title")
            reminder = reminder or ext.get("reminderContent") or ext.get("reminder_content")
            sender = sender or ext.get("senderUserId") or ext.get("sender_user_id")

    custom_data = find_first(decoded, "data")
    if reminder in (None, "") and isinstance(custom_data, str):
        inner = decode_payload(custom_data)
        if isinstance(inner, dict):
            reminder = find_first(inner, "text") or reminder
            text_obj = inner.get("text")
            if isinstance(text_obj, dict):
                reminder = text_obj.get("text") or reminder
            elif isinstance(text_obj, str):
                reminder = text_obj or reminder

    if isinstance(cid, str) and "@" in cid:
        cid = cid.split("@", 1)[0]
    if isinstance(sender, (int, float)):
        sender = str(int(sender))
    if reminder is None:
        reminder = ""
    reminder = str(reminder).strip()
    if not reminder and not cid and not sender:
        return None
    return {
        "conversation_id": str(cid or ""),
        "sender_id": str(sender or ""),
        "sender_name": str(title or ""),
        "text": reminder,
    }


def iter_sync_packages(message: dict) -> list[Any]:
    body = message.get("body") or {}
    packages = (
        _lookup(body, "syncPushPackage")
        or body.get("syncPushPackage")
        or body.get("sync_push_package")
        or {}
    )
    data = packages.get("data") if isinstance(packages, dict) else None
    if isinstance(data, list):
        return [item.get("data") if isinstance(item, dict) else item for item in data]
    if data is not None:
        return [data]
    return []


def is_system_sender(sender_name: str, text: str) -> bool:
    name = sender_name or ""
    if any(token in name for token in ("闲小蜜", "通知消息", "系统消息", "官方")):
        return True
    if text.startswith("[") and "已发货" in text:
        return True
    return False
