"""登录换票追踪：只记摘要，不写 Cookie 值和 token 明文。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlparse

from xianyu.config import DATA_DIR

TRACE_PATH = DATA_DIR / "login_trace.jsonl"


def mask_secret(value: Any, *, keep: int = 4) -> str:
    text = str(value or "")
    if len(text) <= keep:
        return "*" * len(text)
    return text[:keep] + f"...len{len(text)}"


def redact_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    try:
        parsed = urlparse(text)
    except Exception:
        return "unparseable_url"
    keys = ",".join(name for name, _ in parse_qsl(parsed.query, keep_blank_values=True))
    origin = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return f"{origin}?keys={keys}" if keys else origin


def summarize_passport(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"empty": True}
    lowered = {str(key).replace("_", "").lower(): value for key, value in data.items()}

    def pick(*names: str) -> Any:
        for name in names:
            value = lowered.get(name.replace("_", "").lower())
            if value not in (None, "", []):
                return value
        return None

    async_urls = pick("asyncUrls", "asyncUrls", "stUrls")
    return {
        "keys": sorted(str(key) for key in data.keys())[:40],
        "qr_status": pick("qrCodeStatus", "qrCodeStatus", "status"),
        "title": str(pick("title", "msg", "message", "notice") or "")[:160],
        "process_finished": pick("processFinished", "processFinished", "loginSuccess"),
        "iframe_redirect": pick("iframeRedirect", "iframeRedirect"),
        "iframe_url": redact_url(str(pick("iframeRedirectUrl", "iframeRedirectUrl", "redirectUrl") or "")),
        "has_token": bool(pick("token", "lgToken", "loginToken", "st")),
        "async_url_count": len(async_urls) if isinstance(async_urls, list) else 0,
    }


def append_event(
    session_id: str,
    event: str,
    session: Optional[dict] = None,
    **fields: Any,
) -> dict[str, Any]:
    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
        "event": event,
        **fields,
    }
    if session is not None:
        traces = list(session.get("_trace") or [])
        traces.append(record)
        session["_trace"] = traces[-30:]
        session["_last_trace"] = record
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return record


def recent_events(session_id: str, *, limit: int = 40) -> list[dict]:
    if not TRACE_PATH.exists():
        return []
    matched: list[dict] = []
    try:
        for line in TRACE_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(item.get("session_id") or "") == session_id:
                matched.append(item)
    except OSError:
        return []
    return matched[-limit:]


def last_event(session: Optional[dict] = None) -> dict:
    if session and session.get("_last_trace"):
        return dict(session["_last_trace"])
    return {}


def format_trace_line(record: dict) -> str:
    if not record:
        return ""
    parts = [str(record.get("event") or "trace")]
    if record.get("path"):
        parts.append(str(record["path"]))
    if record.get("http_status") is not None:
        parts.append(f"http={record['http_status']}")
    if record.get("new_cookies") is not None:
        names = record.get("new_cookies") or []
        parts.append("new_cookies=" + (",".join(names) if names else "-"))
    if record.get("error"):
        parts.append(f"error={record['error']}")
    summary = record.get("passport") or {}
    if isinstance(summary, dict) and summary.get("title"):
        parts.append(f"msg={summary['title']}")
    if isinstance(summary, dict) and summary.get("qr_status"):
        parts.append(f"qr={summary['qr_status']}")
    return " | ".join(parts)
