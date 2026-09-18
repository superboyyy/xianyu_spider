from fastapi import APIRouter, HTTPException

from xianyu.ai.service import chat
from xianyu.models import AiMessage, AiThread
from xianyu.schemas import AiChatBody
from xianyu.secrets import load_settings, masked_settings, save_keys, save_settings
from xianyu.schemas import SettingsBody

router = APIRouter(tags=["ai"])


@router.get("/settings")
async def get_settings():
    return masked_settings()


@router.put("/settings")
async def put_settings(body: SettingsBody):
    patch = body.model_dump(exclude_none=True)
    key = patch.pop("ai_api_key", None)
    if key:
        save_keys({"ai_api_key": key})
    if "autoreply_mode" in patch and patch["autoreply_mode"] not in {"off", "draft", "send"}:
        raise HTTPException(status_code=400, detail="autoreply_mode 仅支持 off/draft/send")
    return save_settings(patch) | {"has_ai_api_key": masked_settings()["has_ai_api_key"]}


@router.post("/ai/chat")
async def ai_chat(body: AiChatBody):
    try:
        return await chat(body.message, thread_id=body.thread_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ai/threads")
async def list_threads():
    rows = await AiThread.all().order_by("-updated_at").limit(50)
    return {
        "items": [
            {
                "id": row.id,
                "title": row.title,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]
    }


@router.get("/ai/threads/{thread_id}")
async def get_thread(thread_id: int):
    row = await AiThread.get_or_none(id=thread_id)
    if row is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    messages = await AiMessage.filter(thread_id=thread_id).order_by("id")
    return {
        "id": row.id,
        "title": row.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "refs": m.refs,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }
