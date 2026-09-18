from fastapi import APIRouter, HTTPException

from xianyu.models import AutoreplyLog, AutoreplyRule
from xianyu.schemas import AutoreplyRuleBody

router = APIRouter(prefix="/autoreply", tags=["autoreply"])


def _rule_dict(row: AutoreplyRule) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "enabled": row.enabled,
        "match_text": row.match_text,
        "reply_text": row.reply_text,
        "cooldown_seconds": row.cooldown_seconds,
        "only_first": row.only_first,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/rules")
async def list_rules():
    rows = await AutoreplyRule.all().order_by("-id")
    return {"items": [_rule_dict(row) for row in rows]}


@router.post("/rules")
async def create_rule(body: AutoreplyRuleBody):
    row = await AutoreplyRule.create(**body.model_dump())
    return _rule_dict(row)


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: int, body: AutoreplyRuleBody):
    row = await AutoreplyRule.get_or_none(id=rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    await row.save()
    return _rule_dict(row)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: int):
    row = await AutoreplyRule.get_or_none(id=rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    await row.delete()
    return {"ok": True}


@router.get("/logs")
async def list_logs(limit: int = 50):
    rows = await AutoreplyLog.all().order_by("-id").limit(min(limit, 200))
    return {
        "items": [
            {
                "id": row.id,
                "conversation_id": row.conversation_id,
                "rule_id": row.rule_id,
                "mode": row.mode,
                "incoming": row.incoming,
                "reply": row.reply,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }
