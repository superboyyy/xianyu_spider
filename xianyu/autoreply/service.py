"""自动回复：规则优先，本期只出草稿，不实发。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from xianyu.models import AutoreplyLog, AutoreplyRule
from xianyu.secrets import load_settings, normalize_autoreply_mode

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def maybe_autoreply(incoming: dict) -> dict | None:
    settings = load_settings()
    mode = normalize_autoreply_mode(settings.get("autoreply_mode"))
    if mode == "off":
        return None
    text = str(incoming.get("text") or "").strip()
    cid = str(incoming.get("conversation_id") or "").split("@", 1)[0]
    if not text or not cid:
        return None
    rules = await AutoreplyRule.filter(enabled=True)
    matched = None
    for rule in rules:
        needle = (rule.match_text or "").strip()
        if needle and needle.lower() in text.lower():
            matched = rule
            break
    if matched is None:
        return None

    if matched.cooldown_seconds:
        since = _utcnow() - timedelta(seconds=matched.cooldown_seconds)
        recent = await AutoreplyLog.filter(
            conversation_id=cid, rule_id=matched.id, created_at__gte=since
        ).exists()
        if recent:
            return None
    if matched.only_first:
        prior = await AutoreplyLog.filter(conversation_id=cid, rule_id=matched.id).exists()
        if prior:
            return None

    reply = matched.reply_text
    log = await AutoreplyLog.create(
        conversation_id=cid,
        rule_id=matched.id,
        mode="draft",
        incoming=text,
        reply=reply,
        status="draft",
    )
    return {
        "id": log.id,
        "mode": "draft",
        "status": "draft",
        "reply": reply,
        "rule_id": matched.id,
        "conversation_id": cid,
        "sent": False,
    }
