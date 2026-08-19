"""闲鱼 IM 协议辅助：Cookie 解析、消息解码、自动回复匹配。

收发私信走的是闲鱼 Web 端同一套 HTTP(mtop) + WebSocket(LWP) 协议，
不依赖 Playwright。推送体可能是 JSON、Base64 JSON 或 msgpack。
"""

from __future__ import annotations

import base64
import json
import re
import time
import uuid
from typing import Any, Optional
from urllib.parse import parse_qsl, unquote, urlparse


def parse_cookie_header(cookie: str) -> dict[str, str]:
    """把浏览器复制的 Cookie 字符串解析成字典。"""
    result: dict[str, str] = {}
    if not cookie:
        return result
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        if not name:
            continue
        result[name] = value.strip()
    return result


def dump_cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{name}={value}" for name, value in cookies.items() if name)


LOGIN_COOKIE_NAMES = (
    "sgcookie",
    "sgcookie",
    "csg",
    "lgc",
    "havana-lgc0",
    "havana-lgc1",
)

COOKIE_QUERY_ALIAS = {
    "unb": "unb",
    "unb": "unb",
    "uid": "unb",
    "userid": "unb",
    "cookie2": "cookie2",
    "cookie2": "cookie2",
    "cookie1": "cookie1",
    "sgcookie": "sgcookie",
    "sgcookie": "sgcookie",
    "_tb_token_": "_tb_token_",
    "tracknick": "tracknick",
    "_nk_": "_nk_",
    "csg": "csg",
    "lgc": "lgc",
    "havana-lgc0": "havana-lgc0",
    "havana-lgc1": "havana-lgc1",
    "cookie17": "cookie17",
    "wk_cookie2": "wk_cookie2",
    "wk_unb": "wk_unb",
    "_m_h5_tk": "_m_h5_tk",
    "_m_h5_tk_enc": "_m_h5_tk_enc",
    "sn": "sn",
}

RISK_VERIFY_MARKERS = (
    "havana",
    "/iv/",
    "/iv?",
    "verify.htm",
    "verify.html",
    "/verify",
    "punish",
    "h5_verify",
    "identity",
    "aq.taobao",
    "baxia",
    "dialog/view",
    "risk",
)


def cookie_user_id(cookies: dict[str, str]) -> str:
    for key in ("unb", "unb", "userid", "user_id", "uid"):
        value = str(cookies.get(key) or "").strip()
        if value:
            return value
    sn = str(cookies.get("sn") or "").strip()
    if sn.isdigit():
        return sn
    return ""


def has_login_cookies(cookies: dict[str, str]) -> bool:
    """判断 jar 里是否已有闲鱼登录态（不只看 unb）。"""
    if cookie_user_id(cookies):
        return True
    return any(str(cookies.get(name) or "").strip() for name in LOGIN_COOKIE_NAMES)


def cookies_from_query_url(url: str) -> dict[str, str]:
    """从 passport 异步种 Cookie 的 URL query 里抽出登录 Cookie。"""
    if not url or not isinstance(url, str):
        return {}
    try:
        parsed = urlparse(url)
    except Exception:
        return {}
    pairs = list(parse_qsl(parsed.query, keep_blank_values=False))
    fragment = parsed.fragment or ""
    if "=" in fragment:
        if "?" in fragment:
            fragment = fragment.split("?", 1)[1]
        pairs.extend(parse_qsl(fragment, keep_blank_values=False))
    result: dict[str, str] = {}
    for name, value in pairs:
        mapped = COOKIE_QUERY_ALIAS.get(name) or COOKIE_QUERY_ALIAS.get(name.lower())
        if mapped and value:
            result[mapped] = unquote(value)
    return result


def is_risk_verify_url(url: str) -> bool:
    text = (url or "").lower()
    return bool(text) and any(marker in text for marker in RISK_VERIFY_MARKERS)


def is_login_success_url(url: str) -> bool:
    text = (url or "").lower()
    if not text or is_risk_verify_url(text):
        return False
    return any(host in text for host in ("goofish.com", "taobao.com", "tmall.com", "alipay.com"))


def collect_async_urls(data: dict) -> list[str]:
    """收集官方用来同步种 Cookie 的 asyncUrls / st 地址。"""
    urls: list[str] = []
    if not isinstance(data, dict):
        return urls
    for key, val in data.items():
        compact = str(key).replace("_", "").lower()
        if compact not in {"asyncurls", "sturl", "sturls", "syncurls"}:
            continue
        candidates = val if isinstance(val, list) else [val]
        for item in candidates:
            text = str(item or "").strip()
            if text.startswith("http"):
                urls.append(text)
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def passport_flag(data: dict, *names: str) -> Any:
    """按字段名大小写不敏感取值。"""
    if not isinstance(data, dict):
        return None
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def normalize_qr_status(status: str) -> str:
    """闲鱼官方状态是 NEW / SCANED（一个 N）/ CONFIRMED / EXPIRED / CANCELED。"""
    raw = (status or "").strip()
    key = raw.upper().replace("-", "_")
    mapping = {
        "NEW": "new",
        "WAIT": "new",
        "WAITING": "new",
        "SCAN": "scanned",
        "SCANED": "scanned",
        "SCANNED": "scanned",
        "CONFIRMED": "confirmed",
        "SUCCESS": "confirmed",
        "PASSED": "confirmed",
        "OK": "confirmed",
        "EXPIRED": "expired",
        "EXPIRE": "expired",
        "CANCELED": "canceled",
        "CANCELLED": "canceled",
    }
    return mapping.get(key, raw.lower() or "new")


def is_qr_confirmed(status: str) -> bool:
    return normalize_qr_status(status) == "confirmed"


def qr_status_hint(status: str) -> str:
    mapped = normalize_qr_status(status)
    hints = {
        "new": "等待扫描，请用闲鱼 App 扫码。",
        "scanned": "已扫码，请在闲鱼 App 里点「确认登录」。只扫码不会登录。",
        "confirmed": "已在 App 确认，正在换取登录 Cookie。",
        "expired": "二维码已过期，请重新调用 POST /auth/qr/start。",
        "canceled": "已取消登录，请重新生成二维码。",
    }
    return hints.get(mapped, f"当前状态: {mapped}")


def build_device_id(user_id: str) -> str:
    uid = user_id or "0"
    return f"{uuid.uuid4()}-{uid}"


def generate_mid() -> str:
    return f"{int(time.time() * 1000)}{uuid.uuid4().hex[:8]}"


def generate_uuid() -> str:
    return f"-{int(time.time() * 1000)}{uuid.uuid4().int % 10}"


def _b64decode(data: str) -> bytes:
    padded = data.replace("-", "+").replace("_", "/")
    padded += "=" * ((4 - len(padded) % 4) % 4)
    return base64.b64decode(padded)


def decode_payload(data: Any) -> Any:
    """尽量把同步推送里的 data 解成 dict/list。"""
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

        unpacked = msgpack.unpackb(raw, raw=False, strict_map_key=False)
        return unpacked
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
    """深度优先搜索第一个匹配字段。"""
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
    """从同步推送/会话消息中抽出会话、发送者和文本。"""
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
    """取出 /s/sync 推送里的 data 列表。"""
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


def match_auto_reply(text: str, default_reply: str, keyword_replies: list[dict]) -> Optional[str]:
    """按关键词匹配回复；没有命中则用默认回复。空文本不回。"""
    content = (text or "").strip()
    if not content:
        return None
    for item in keyword_replies or []:
        keyword = str(item.get("keyword") or "").strip()
        reply = str(item.get("reply") or "").strip()
        if keyword and reply and keyword in content:
            return reply
    default = (default_reply or "").strip()
    return default or None


def render_reply(template: str, incoming: dict[str, str]) -> str:
    """支持简单占位符：{sender_name} {text} {conversation_id}。"""
    mapping = {
        "sender_name": incoming.get("sender_name") or "买家",
        "text": incoming.get("text") or "",
        "conversation_id": incoming.get("conversation_id") or "",
        "sender_id": incoming.get("sender_id") or "",
    }

    def repl(match: re.Match) -> str:
        return str(mapping.get(match.group(1), match.group(0)))

    return re.sub(r"\{(sender_name|text|conversation_id|sender_id)\}", repl, template)
