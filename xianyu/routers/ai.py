from fastapi import APIRouter, HTTPException

from xianyu.ai.providers import list_providers, resolve_config
from xianyu.ai.service import chat
from xianyu.models import AiMessage, AiThread
from xianyu.schemas import AiChatBody, SettingsBody
from xianyu.secrets import masked_settings, normalize_autoreply_mode, save_keys, save_settings

router = APIRouter(tags=["ai"])


@router.get("/settings")
async def get_settings():
    cfg = resolve_config()
    return masked_settings() | {
        "resolved_provider": cfg.provider_id,
        "resolved_label": cfg.label,
        "resolved_base_url": cfg.base_url,
        "resolved_model": cfg.model,
        "needs_key": cfg.needs_key,
        "can_call": cfg.can_call,
    }


@router.get("/ai/providers")
async def ai_providers():
    return {"items": list_providers()}


@router.put("/settings")
async def put_settings(body: SettingsBody):
    patch = body.model_dump(exclude_none=True)
    key = patch.pop("ai_api_key", None)
    if key:
        save_keys({"ai_api_key": key})
    if "autoreply_mode" in patch:
        if str(patch["autoreply_mode"]).strip().lower() == "send":
            patch["autoreply_mode"] = "draft"
        elif normalize_autoreply_mode(patch["autoreply_mode"]) != str(patch["autoreply_mode"]).strip().lower():
            raise HTTPException(status_code=400, detail="autoreply_mode 本期仅支持 off / draft")
        patch["autoreply_mode"] = normalize_autoreply_mode(patch["autoreply_mode"])
    saved = save_settings(patch)
    return saved | {
        "has_ai_api_key": masked_settings()["has_ai_api_key"],
        "hint": "自动回复本期只写草稿，不会实发。" if saved.get("autoreply_mode") == "draft" else "",
    }


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
