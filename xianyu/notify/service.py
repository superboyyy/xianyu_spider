"""推送适配：Bark / 通用 Webhook。"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

from xianyu.models import NotifyChannel, NotifyEvent

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fingerprint(event_type: str, *parts: Any) -> str:
    raw = "|".join([event_type, *[str(p or "") for p in parts]])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


async def recently_notified(fp: str, *, hours: int = 12) -> bool:
    since = _utcnow() - timedelta(hours=hours)
    return await NotifyEvent.filter(fingerprint=fp, created_at__gte=since, ok=True).exists()


async def send_bark(endpoint: str, title: str, body: str) -> None:
    text = (endpoint or "").strip().rstrip("/")
    if not text:
        raise ValueError("Bark endpoint 为空")
    if text.startswith("http://") or text.startswith("https://"):
        if "api.day.app" in text and text.rstrip("/").count("/") <= 3:
            url = f"{text.rstrip('/')}/{quote(title)}/{quote(body)}"
        elif text.count("/") >= 4 and not text.endswith(".json"):
            url = f"{text}/{quote(title)}/{quote(body)}"
        else:
            url = text
    else:
        url = f"https://api.day.app/{text}/{quote(title)}/{quote(body)}"
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(url)
        res.raise_for_status()


async def send_webhook(endpoint: str, title: str, body: str, payload: dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(
            endpoint,
            json={"title": title, "body": body, "payload": payload},
        )
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
            if channel.kind == "bark":
                await send_bark(channel.endpoint, title, body)
            elif channel.kind == "webhook":
                await send_webhook(channel.endpoint, title, body, data)
            else:
                raise ValueError(f"不支持的渠道: {channel.kind}")
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
