"""自动回复：规则优先，默认草稿。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from xianyu.models import AutoreplyLog, AutoreplyRule
from xianyu.secrets import load_settings

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def maybe_autoreply(incoming: dict) -> dict | None:
    settings = load_settings()
    mode = settings.get("autoreply_mode") or "off"
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
    status = "draft"
    if mode == "send":
        try:
            from xianyu.im_service import im_service

            await im_service.send_text(
                conversation_id=cid,
                to_user_id=str(incoming.get("sender_id") or cid),
                text=reply,
                source="rule",
            )
            status = "sent"
        except Exception as exc:
            logger.exception("自动回复发送失败")
            status = f"error:{exc}"
    log = await AutoreplyLog.create(
        conversation_id=cid,
        rule_id=matched.id,
        mode=mode,
        incoming=text,
        reply=reply,
        status=status,
    )
    return {
        "id": log.id,
        "mode": mode,
        "status": status,
        "reply": reply,
        "rule_id": matched.id,
        "conversation_id": cid,
    }
