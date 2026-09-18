"""推送适配：Bark / Webhook / ntfy / Telegram / Server酱 / 企业微信。"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

from xianyu.models import NotifyChannel, NotifyEvent

logger = logging.getLogger(__name__)

CHANNEL_KINDS = ("bark", "webhook", "ntfy", "telegram", "serverchan", "wecom")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fingerprint(event_type: str, *parts: Any) -> str:
    raw = "|".join([event_type, *[str(p or "") for p in parts]])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


async def recently_notified(fp: str, *, hours: int = 12) -> bool:
    since = _utcnow() - timedelta(hours=hours)
    return await NotifyEvent.filter(fingerprint=fp, created_at__gte=since, ok=True).exists()


def prepare_request(
    kind: str,
    endpoint: str,
    title: str,
    body: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kind = (kind or "").strip().lower()
    text = (endpoint or "").strip()
    if not text:
        raise ValueError("通知 endpoint 为空")
    if kind == "bark":
        return _prepare_bark(text, title, body)
    if kind == "webhook":
        return {
            "method": "POST",
            "url": text,
            "json": {"title": title, "body": body, "payload": payload or {}},
        }
    if kind == "ntfy":
        return _prepare_ntfy(text, title, body)
    if kind == "telegram":
        return _prepare_telegram(text, title, body)
    if kind == "serverchan":
        return _prepare_serverchan(text, title, body)
    if kind == "wecom":
        return _prepare_wecom(text, title, body)
    raise ValueError(f"不支持的渠道: {kind}")


def _prepare_bark(text: str, title: str, body: str) -> dict[str, Any]:
    raw = text.rstrip("/")
    if raw.startswith("http://") or raw.startswith("https://"):
        if "api.day.app" in raw and raw.count("/") <= 3:
            url = f"{raw}/{quote(title)}/{quote(body)}"
        elif raw.count("/") >= 4 and not raw.endswith(".json"):
            url = f"{raw}/{quote(title)}/{quote(body)}"
        else:
            url = raw
    else:
        url = f"https://api.day.app/{raw}/{quote(title)}/{quote(body)}"
    return {"method": "GET", "url": url}


def _prepare_ntfy(text: str, title: str, body: str) -> dict[str, Any]:
    token = ""
    target = text
    if " " in text and not text.startswith("http"):
        token, target = text.split(" ", 1)
    if not target.startswith("http://") and not target.startswith("https://"):
        target = f"https://ntfy.sh/{target.lstrip('/')}"
    headers = {"Title": title, "Content-Type": "text/plain; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return {"method": "POST", "url": target, "content": body, "headers": headers}


def _prepare_telegram(text: str, title: str, body: str) -> dict[str, Any]:
    token = ""
    chat_id = ""
    if text.startswith("http://") or text.startswith("https://"):
        url = text
        return {
            "method": "POST",
            "url": url,
            "json": {"text": f"{title}\n{body}", "disable_web_page_preview": True},
        }
    if "|" in text:
        token, chat_id = text.split("|", 1)
    elif "@" in text:
        token, chat_id = text.rsplit("@", 1)
    else:
        raise ValueError("Telegram 请填 token|chat_id，或完整 sendMessage URL")
    token = token.strip()
    if token.startswith("bot"):
        token = token[3:]
    return {
        "method": "POST",
        "url": f"https://api.telegram.org/bot{token}/sendMessage",
        "json": {"chat_id": chat_id.strip(), "text": f"{title}\n{body}", "disable_web_page_preview": True},
    }


def _prepare_serverchan(text: str, title: str, body: str) -> dict[str, Any]:
    key = text
    if text.startswith("http://") or text.startswith("https://"):
        url = text
    else:
        url = f"https://sctapi.ftqq.com/{key}.send"
    return {"method": "POST", "url": url, "data": {"title": title, "desp": body}}


def _prepare_wecom(text: str, title: str, body: str) -> dict[str, Any]:
    if text.startswith("http://") or text.startswith("https://"):
        url = text
    else:
        url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={text}"
    return {
        "method": "POST",
        "url": url,
        "json": {"msgtype": "text", "text": {"content": f"{title}\n{body}"}},
    }


async def send_prepared(req: dict[str, Any]) -> None:
    method = str(req.get("method") or "POST").upper()
    kwargs: dict[str, Any] = {}
    if req.get("headers"):
        kwargs["headers"] = req["headers"]
    if "json" in req:
        kwargs["json"] = req["json"]
    if "data" in req:
        kwargs["data"] = req["data"]
    if "content" in req:
        kwargs["content"] = req["content"]
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.request(method, req["url"], **kwargs)
        res.raise_for_status()


async def dispatch_notify(
    *,
    event_type: str,
    title: str,
    body: str,
    fingerprint_key: str,
    payload: dict[str, Any] | None = None,
    dedupe_hours: int = 12,
) -> list[dict[str, Any]]:
    if dedupe_hours > 0 and await recently_notified(fingerprint_key, hours=dedupe_hours):
        return [{"skipped": True, "reason": "deduped", "fingerprint": fingerprint_key}]
    channels = await NotifyChannel.filter(enabled=True)
    results: list[dict[str, Any]] = []
    data = payload or {}
    if not channels:
        event = await NotifyEvent.create(
            channel_id=None,
            event_type=event_type,
            fingerprint=fingerprint_key,
            title=title,
            body=body,
            payload=data,
            ok=False,
            error="没有启用的通知渠道",
        )
        return [{"id": event.id, "ok": False, "error": event.error}]
    for channel in channels:
        ok = False
        error = ""
        try:
            req = prepare_request(channel.kind, channel.endpoint, title, body, data)
            await send_prepared(req)
            ok = True
        except Exception as exc:
            error = str(exc)
            logger.exception("通知失败 channel=%s", channel.id)
        event = await NotifyEvent.create(
            channel_id=channel.id,
            event_type=event_type,
            fingerprint=fingerprint_key,
            title=title,
            body=body,
            payload=data,
            ok=ok,
            error=error,
        )
        results.append({"id": event.id, "channel_id": channel.id, "ok": ok, "error": error})
    return results
