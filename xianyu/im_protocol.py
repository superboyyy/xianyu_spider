"""闲鱼 IM 推送解码：LWP JSON / Base64 JSON / Base64 MessagePack。"""

from __future__ import annotations

import base64
import json
import random
import re
import struct
import time
from typing import Any, Optional

B64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
CID_RE = re.compile(r"(\d{5,})@goofish")


def generate_mid() -> str:
    # 对齐网页 IM：`{random}{timestamp} 0`
    return f"{int(1000 * random.random())}{int(time.time() * 1000)} 0"


def generate_uuid() -> str:
    return f"-{int(time.time() * 1000)}1"


def _b64decode(data: str) -> bytes:
    padded = data.replace("-", "+").replace("_", "/")
    padded += "=" * ((4 - len(padded) % 4) % 4)
    return base64.b64decode(padded)


def _looks_like_base64(text: str) -> bool:
    cleaned = "".join(ch for ch in text if ch in B64_CHARS)
    if len(cleaned) < 16:
        return False
    return len(cleaned) >= len(text.strip()) * 0.85


class MessagePackDecoder:
    """纯 Python MessagePack。映射截断时返回已读部分，不把乱码当聊天。"""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.length = len(data)

    def read_byte(self) -> int:
        if self.pos >= self.length:
            raise ValueError("incomplete msgpack")
        byte = self.data[self.pos]
        self.pos += 1
        return byte

    def read_bytes(self, count: int) -> bytes:
        if count < 0 or self.pos + count > self.length:
            raise ValueError("incomplete msgpack")
        result = self.data[self.pos : self.pos + count]
        self.pos += count
        return result

    def read_string(self, length: int) -> str:
        raw = self.read_bytes(length)
        return raw.decode("utf-8", errors="replace")

    def decode_array(self, size: int) -> list[Any]:
        result: list[Any] = []
        for _ in range(size):
            try:
                result.append(self.decode_value())
            except ValueError:
                break
        return result

    def decode_map(self, size: int) -> dict[Any, Any]:
        result: dict[Any, Any] = {}
        for _ in range(size):
            try:
                key = self.decode_value()
                value = self.decode_value()
            except ValueError:
                break
            result[key] = value
        return result

    def decode_value(self) -> Any:
        format_byte = self.read_byte()
        if format_byte <= 0x7F:
            return format_byte
        if 0x80 <= format_byte <= 0x8F:
            return self.decode_map(format_byte & 0x0F)
        if 0x90 <= format_byte <= 0x9F:
            return self.decode_array(format_byte & 0x0F)
        if 0xA0 <= format_byte <= 0xBF:
            return self.read_string(format_byte & 0x1F)
        if format_byte == 0xC0:
            return None
        if format_byte == 0xC2:
            return False
        if format_byte == 0xC3:
            return True
        if format_byte == 0xC4:
            return self.read_bytes(self.read_byte())
        if format_byte == 0xC5:
            return self.read_bytes(struct.unpack(">H", self.read_bytes(2))[0])
        if format_byte == 0xC6:
            return self.read_bytes(struct.unpack(">I", self.read_bytes(4))[0])
        if format_byte == 0xCA:
            return struct.unpack(">f", self.read_bytes(4))[0]
        if format_byte == 0xCB:
            return struct.unpack(">d", self.read_bytes(8))[0]
        if format_byte == 0xCC:
            return self.read_byte()
        if format_byte == 0xCD:
            return struct.unpack(">H", self.read_bytes(2))[0]
        if format_byte == 0xCE:
            return struct.unpack(">I", self.read_bytes(4))[0]
        if format_byte == 0xCF:
            return struct.unpack(">Q", self.read_bytes(8))[0]
        if format_byte == 0xD0:
            return struct.unpack(">b", self.read_bytes(1))[0]
        if format_byte == 0xD1:
            return struct.unpack(">h", self.read_bytes(2))[0]
        if format_byte == 0xD2:
            return struct.unpack(">i", self.read_bytes(4))[0]
        if format_byte == 0xD3:
            return struct.unpack(">q", self.read_bytes(8))[0]
        if format_byte == 0xD9:
            return self.read_string(self.read_byte())
        if format_byte == 0xDA:
            return self.read_string(struct.unpack(">H", self.read_bytes(2))[0])
        if format_byte == 0xDB:
            return self.read_string(struct.unpack(">I", self.read_bytes(4))[0])
        if format_byte == 0xDC:
            return self.decode_array(struct.unpack(">H", self.read_bytes(2))[0])
        if format_byte == 0xDD:
            return self.decode_array(struct.unpack(">I", self.read_bytes(4))[0])
        if format_byte == 0xDE:
            return self.decode_map(struct.unpack(">H", self.read_bytes(2))[0])
        if format_byte == 0xDF:
            return self.decode_map(struct.unpack(">I", self.read_bytes(4))[0])
        if format_byte >= 0xE0:
            return format_byte - 256
        raise ValueError(f"unknown msgpack format 0x{format_byte:02x}")


def unpack_msgpack(raw: bytes) -> Any:
    try:
        return MessagePackDecoder(raw).decode_value()
    except ValueError:
        return None


def pack_msgpack(value: Any) -> bytes:
    if value is None:
        return b"\xc0"
    if value is False:
        return b"\xc2"
    if value is True:
        return b"\xc3"
    if isinstance(value, int) and not isinstance(value, bool):
        if 0 <= value <= 127:
            return bytes([value])
        if -32 <= value < 0:
            return bytes([value & 0xFF])
        if 0 <= value <= 255:
            return b"\xcc" + bytes([value])
        if 0 <= value <= 65535:
            return b"\xcd" + struct.pack(">H", value)
        if 0 <= value <= 0xFFFFFFFF:
            return b"\xce" + struct.pack(">I", value)
        if value > 0:
            return b"\xcf" + struct.pack(">Q", value)
        if -128 <= value:
            return b"\xd0" + struct.pack(">b", value)
        if -32768 <= value:
            return b"\xd1" + struct.pack(">h", value)
        if -2147483648 <= value:
            return b"\xd2" + struct.pack(">i", value)
        return b"\xd3" + struct.pack(">q", value)
    if isinstance(value, str):
        raw = value.encode("utf-8")
        n = len(raw)
        if n <= 31:
            return bytes([0xA0 | n]) + raw
        if n <= 255:
            return b"\xd9" + bytes([n]) + raw
        if n <= 65535:
            return b"\xda" + struct.pack(">H", n) + raw
        return b"\xdb" + struct.pack(">I", n) + raw
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        n = len(raw)
        if n <= 255:
            return b"\xc4" + bytes([n]) + raw
        if n <= 65535:
            return b"\xc5" + struct.pack(">H", n) + raw
        return b"\xc6" + struct.pack(">I", n) + raw
    if isinstance(value, dict):
        items = list(value.items())
        n = len(items)
        if n <= 15:
            header = bytes([0x80 | n])
        elif n <= 65535:
            header = b"\xde" + struct.pack(">H", n)
        else:
            header = b"\xdf" + struct.pack(">I", n)
        return header + b"".join(pack_msgpack(k) + pack_msgpack(v) for k, v in items)
    if isinstance(value, (list, tuple)):
        n = len(value)
        if n <= 15:
            header = bytes([0x90 | n])
        elif n <= 65535:
            header = b"\xdc" + struct.pack(">H", n)
        else:
            header = b"\xdd" + struct.pack(">I", n)
        return header + b"".join(pack_msgpack(item) for item in value)
    raise TypeError(f"unsupported msgpack type: {type(value)!r}")


def decode_bytes(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is not None:
        stripped = text.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
    unpacked = unpack_msgpack(raw)
    if unpacked is not None:
        return unpacked
    recovered = recover_from_bytes(raw)
    return recovered


def decrypt(data: str) -> Any:
    cleaned = "".join(ch for ch in data if ch in B64_CHARS)
    if not cleaned:
        return None
    cleaned += "=" * ((4 - len(cleaned) % 4) % 4)
    try:
        raw = base64.b64decode(cleaned)
    except Exception:
        return None
    return decode_bytes(raw)


def decode_payload(data: Any) -> Any:
    if data is None or isinstance(data, (dict, list, int, float, bool)):
        return data
    if isinstance(data, (bytes, bytearray)):
        return decode_bytes(bytes(data))
    if not isinstance(data, str):
        return data
    text = data.strip()
    if not text:
        return None
    if text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    if _looks_like_base64(text):
        return decrypt(text)
    return None


def recover_from_bytes(raw: bytes) -> Optional[dict[str, Any]]:
    text = raw.decode("utf-8", errors="ignore")
    reminder = _json_field(text, "reminderContent")
    if not reminder:
        match = re.search(
            r'"text"\s*:\s*\{\s*"text"\s*:\s*"((?:\\.|[^"\\])*)"',
            text,
        )
        reminder = _unescape(match.group(1)) if match else ""
    if not reminder:
        return None
    title = _json_field(text, "reminderTitle")
    sender = _json_field(text, "senderUserId")
    cid_match = CID_RE.search(text)
    cid = cid_match.group(0) if cid_match else ""
    return {
        1: {
            2: cid,
            10: {
                "reminderTitle": title,
                "senderUserId": sender,
                "reminderContent": reminder,
            },
        }
    }


def _json_field(text: str, name: str) -> str:
    match = re.search(rf'"{re.escape(name)}"\s*:\s*"((?:\\.|[^"\\])*)"', text)
    return _unescape(match.group(1)) if match else ""


def _unescape(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value


def inflate(node: Any) -> Any:
    """把嵌套的 JSON 字符串 / Base64 包展开成 dict，方便抽字段。"""
    if isinstance(node, dict):
        return {key: inflate(value) for key, value in node.items()}
    if isinstance(node, list):
        return [inflate(value) for value in node]
    if isinstance(node, str):
        text = node.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return inflate(json.loads(text))
            except json.JSONDecodeError:
                return node
        if _looks_like_base64(text):
            nested = decrypt(text)
            if isinstance(nested, (dict, list)):
                return inflate(nested)
        return node
    return node


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


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return _as_text(value.get("text"))
    if isinstance(value, (int, float, bool)):
        return ""
    text = str(value).strip()
    if text.startswith("{") or text.startswith("["):
        return ""
    return text


def extract_incoming_message(payload: Any) -> Optional[dict[str, str]]:
    decoded = inflate(decode_payload(payload))
    if not isinstance(decoded, dict):
        return None

    reminder = _as_text(find_first(decoded, "reminderContent", "reminder_content"))
    title = _as_text(find_first(decoded, "reminderTitle", "reminder_title"))
    sender = find_first(decoded, "senderUserId", "sender_user_id", "senderId")
    cid = find_first(decoded, "cid", "conversationId", "conversation_id")

    numbered = _lookup(decoded, 1)
    if isinstance(numbered, dict):
        cid = cid or _lookup(numbered, 2) or _lookup(numbered, "2")
        ext = _lookup(numbered, 10) or _lookup(numbered, "10")
        if isinstance(ext, dict):
            title = title or _as_text(ext.get("reminderTitle") or ext.get("reminder_title"))
            reminder = reminder or _as_text(
                ext.get("reminderContent") or ext.get("reminder_content")
            )
            sender = sender or ext.get("senderUserId") or ext.get("sender_user_id")
        one = _lookup(numbered, 1)
        if sender in (None, "") and isinstance(one, str) and "@goofish" in one:
            sender = one.split("@", 1)[0]
        elif sender in (None, "") and isinstance(one, dict):
            nested = _lookup(one, 1)
            if isinstance(nested, str):
                sender = nested.split("@", 1)[0]

    if not reminder:
        reminder = _as_text(find_first(decoded, "text"))

    if isinstance(cid, str) and "@" in cid:
        cid = cid.split("@", 1)[0]
    elif isinstance(cid, (int, float)):
        cid = str(int(cid))
    if isinstance(sender, (int, float)):
        sender = str(int(sender))
    elif isinstance(sender, str) and "@" in sender:
        sender = sender.split("@", 1)[0]

    reminder = (reminder or "").strip()
    if not reminder:
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
