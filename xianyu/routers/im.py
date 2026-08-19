import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from xianyu.im_worker import im_service
from xianyu.models import ChatMessage, ReplySetting
from xianyu.mtop import login_snapshot
from xianyu.schemas import AutoReplyBody

router = APIRouter(prefix="/im", tags=["im"])


async def _reply_setting() -> ReplySetting:
    setting = await ReplySetting.get_or_none(id=1)
    if setting is None:
        setting = await ReplySetting.create(id=1)
    return setting


def _setting_payload(setting: ReplySetting) -> dict:
    try:
        keywords = json.loads(setting.keywords_json or "[]")
    except json.JSONDecodeError:
        keywords = []
    return {
        "enabled": setting.enabled,
        "default_reply": setting.default_reply,
        "keyword_replies": keywords,
        "webhook_url": setting.webhook_url,
    }


@router.get("/config", summary="读取自动回复配置")
async def get_im_config():
    return _setting_payload(await _reply_setting())


@router.put("/config", summary="更新自动回复与 Webhook 通知")
async def put_im_config(body: AutoReplyBody):
    setting = await _reply_setting()
    if body.enabled is not None:
        setting.enabled = body.enabled
    if body.default_reply is not None:
        setting.default_reply = body.default_reply
    if body.keyword_replies is not None:
        setting.keywords_json = json.dumps(
            [item.model_dump() for item in body.keyword_replies],
            ensure_ascii=False,
        )
    if body.webhook_url is not None:
        setting.webhook_url = body.webhook_url
    await setting.save()
    return _setting_payload(setting)


@router.post("/start", summary="开始监听消息并自动回复")
async def im_start():
    snapshot = login_snapshot()
    if not snapshot.get("logged_in"):
        raise HTTPException(status_code=401, detail="请先通过 /auth/cookie 或扫码登录")
    return await im_service.start()


@router.post("/stop", summary="停止监听")
async def im_stop():
    return await im_service.stop()


@router.get("/status", summary="IM 监听状态")
async def im_status():
    return im_service.status() | {"login": login_snapshot()}


@router.get("/messages", summary="最近收到的消息")
async def im_messages(limit: int = Query(50, ge=1, le=200)):
    rows = await ChatMessage.all().order_by("-id").limit(limit)
    return [
        {
            "id": row.id,
            "conversation_id": row.conversation_id,
            "sender_id": row.sender_id,
            "sender_name": row.sender_name,
            "content": row.content,
            "direction": row.direction,
            "replied": row.replied,
            "reply_text": row.reply_text,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/events", summary="SSE 实时通知（收到消息/已回复）")
async def im_events():
    queue = im_service.subscribe()

    async def generate():
        try:
            yield 'data: {"event":"connected"}\n\n'
            while True:
                item = await queue.get()
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            im_service.unsubscribe(queue)

    return StreamingResponse(generate(), media_type="text/event-stream")
