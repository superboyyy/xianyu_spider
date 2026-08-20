import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from xianyu.im_service import im_service
from xianyu.mtop import LoginRequired, require_login
from xianyu.schemas import SendMessageBody

router = APIRouter(prefix="/im", tags=["im"])


def _login_http(exc: LoginRequired) -> HTTPException:
    return HTTPException(status_code=401, detail=str(exc))


@router.post("/start", summary="连接闲鱼 IM（需登录）")
async def im_start():
    try:
        snapshot = await require_login()
    except LoginRequired as exc:
        raise _login_http(exc) from exc
    status = await im_service.start()
    return status | {"logged_in": True, "login_user_id": snapshot.get("user_id") or ""}


@router.post("/stop", summary="断开 IM")
async def im_stop():
    return await im_service.stop()


@router.get("/status", summary="IM 连接状态")
async def im_status():
    return im_service.status()


@router.get("/conversations", summary="本地会话列表（本次服务收到的）")
async def im_conversations(limit: int = Query(50, ge=1, le=200)):
    return await im_service.list_conversations(limit=limit)


@router.get("/messages", summary="本地消息（可按会话过滤）")
async def im_messages(
    conversation_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    return await im_service.list_messages(conversation_id=conversation_id, limit=limit)


@router.post("/send", summary="发送文本（需登录且已 start）")
async def im_send(body: SendMessageBody):
    try:
        await require_login()
    except LoginRequired as exc:
        raise _login_http(exc) from exc
    try:
        return await im_service.send_text(
            conversation_id=body.conversation_id,
            to_user_id=body.to_user_id,
            text=body.text,
            source=body.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/events", summary="SSE：message.received / message.sent")
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
