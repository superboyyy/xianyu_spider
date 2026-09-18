from fastapi import APIRouter, HTTPException

from xianyu.models import NotifyChannel, NotifyEvent
from xianyu.notify.service import dispatch_notify, fingerprint
from xianyu.schemas import NotifyChannelBody, NotifyTestBody

router = APIRouter(prefix="/notify", tags=["notify"])


def _channel_dict(row: NotifyChannel) -> dict:
    endpoint = row.endpoint
    masked = endpoint if len(endpoint) < 8 else endpoint[:4] + "…" + endpoint[-4:]
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "endpoint_masked": masked,
        "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/channels")
async def list_channels():
    rows = await NotifyChannel.all().order_by("-id")
    return {"items": [_channel_dict(row) for row in rows]}


@router.post("/channels")
async def create_channel(body: NotifyChannelBody):
    kind = (body.kind or "bark").strip().lower()
    if kind not in {"bark", "webhook"}:
        raise HTTPException(status_code=400, detail="kind 仅支持 bark / webhook")
    row = await NotifyChannel.create(
        name=body.name or kind,
        kind=kind,
        endpoint=body.endpoint.strip(),
        enabled=body.enabled,
    )
    return _channel_dict(row)


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int):
    row = await NotifyChannel.get_or_none(id=channel_id)
    if row is None:
        raise HTTPException(status_code=404, detail="渠道不存在")
    await row.delete()
    return {"ok": True}


@router.post("/test")
async def test_notify(body: NotifyTestBody):
    fp = fingerprint("test", body.title, body.body)
    results = await dispatch_notify(
        event_type="test",
        title=body.title,
        body=body.body,
        fingerprint_key=fp,
        dedupe_hours=0,
        payload={"test": True},
    )
    return {"results": results}


@router.get("/events")
async def list_events(limit: int = 50):
    rows = await NotifyEvent.all().order_by("-id").limit(min(limit, 200))
    return {
        "items": [
            {
                "id": row.id,
                "channel_id": row.channel_id,
                "event_type": row.event_type,
                "title": row.title,
                "body": row.body,
                "ok": row.ok,
                "error": row.error,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }
