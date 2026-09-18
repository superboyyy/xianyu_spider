"""AI 问询：OpenAI 兼容 + 本机工具。"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from xianyu.catalog import attach_saved_ids, product_to_public, public_from_raw
from xianyu.models import AiMessage, AiThread, PriceSnapshot, XianyuProduct
from xianyu.pricing import parse_price, summarize_prices
from xianyu.search import save_to_db, scrape_xianyu_http
from xianyu.search_query import SearchFilters
from xianyu.secrets import get_key, load_settings

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_items",
            "description": "按关键词搜索闲鱼商品并写入本机货架",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "city": {"type": "string"},
                    "min_price": {"type": "integer"},
                    "max_price": {"type": "integer"},
                    "max_pages": {"type": "integer"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "price_stats",
            "description": "基于本机货架/价格快照计算均价、中位数等（非全网官方行情）",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "days": {"type": "integer"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend",
            "description": "从本机货架里挑出较合适的商品并给出入手倾向",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "budget": {"type": "number"},
                    "limit": {"type": "integer"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_im",
            "description": "起草一条私信，不发送",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "item_title": {"type": "string"},
                },
                "required": ["goal"],
            },
        },
    },
]


async def _tool_search(args: dict[str, Any]) -> dict[str, Any]:
    filters = SearchFilters(
        sort="newest",
        min_price=args.get("min_price"),
        max_price=args.get("max_price"),
        city=(args.get("city") or None),
    )
    raw = await scrape_xianyu_http(args["keyword"], int(args.get("max_pages") or 1), filters=filters)
    items = [public_from_raw(item) for item in raw]
    new_ids: list[int] = []
    if raw:
        _, new_ids = await save_to_db(raw)
        items = await attach_saved_ids(items, new_ids)
    return {"total": len(items), "items": items[:12], "new_records": len(new_ids)}


async def _tool_stats(args: dict[str, Any]) -> dict[str, Any]:
    keyword = str(args.get("keyword") or "").strip()
    rows = await XianyuProduct.filter(title__icontains=keyword).limit(200)
    values = [parse_price(row.price) for row in rows]
    values = [v for v in values if v is not None]
    snaps = await PriceSnapshot.filter(keyword__icontains=keyword).order_by("-id").limit(300)
    snap_values = [s.price_value for s in snaps if s.price_value is not None]
    merged = values + snap_values
    stats = summarize_prices(merged)
    stats["disclaimer"] = "基于本机搜索/货架样本，不是全网官方行情"
    stats["keyword"] = keyword
    return stats


async def _tool_recommend(args: dict[str, Any]) -> dict[str, Any]:
    keyword = str(args.get("keyword") or "").strip()
    budget = args.get("budget")
    limit = min(int(args.get("limit") or 5), 10)
    rows = await XianyuProduct.filter(title__icontains=keyword).order_by("-id").limit(80)
    scored = []
    stats = summarize_prices([parse_price(r.price) for r in rows if parse_price(r.price) is not None])
    median = stats.get("median")
    for row in rows:
        value = parse_price(row.price)
        if value is None:
            continue
        if budget is not None and value > float(budget):
            continue
        score = 60
        reasons = []
        risks = []
        if median:
            if value <= median * 0.85:
                score += 20
                reasons.append(f"低于样本中位 {median:g}")
            elif value >= median * 1.15:
                score -= 15
                risks.append("高于样本中位")
        if budget is not None and value <= float(budget) * 0.9:
            score += 10
            reasons.append("在预算内且有余量")
        if not row.image_url:
            score -= 5
            risks.append("缺少图片")
        verdict = "buy" if score >= 75 else "wait" if score >= 55 else "skip"
        scored.append(
            {
                "item": product_to_public(row),
                "score": score,
                "verdict": verdict,
                "reasons": reasons,
                "risks": risks,
                "price_value": value,
            }
        )
    scored.sort(key=lambda x: (-x["score"], x["price_value"]))
    return {"stats": stats, "items": scored[:limit], "disclaimer": "基于本机样本的启发式判断"}


def _tool_draft(args: dict[str, Any]) -> dict[str, Any]:
    goal = str(args.get("goal") or "问问还在不在")
    title = str(args.get("item_title") or "这个")
    text = f"你好，看到你发布的「{title}」，想确认一下还在吗？{goal}。方便的话回一下，谢谢。"
    return {"draft": text, "sent": False}


async def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "search_items":
        return await _tool_search(args)
    if name == "price_stats":
        return await _tool_stats(args)
    if name == "recommend":
        return await _tool_recommend(args)
    if name == "draft_im":
        return _tool_draft(args)
    return {"error": f"未知工具 {name}"}


def _ai_config() -> tuple[str, str, str]:
    settings = load_settings()
    base = (
        settings.get("ai_base_url")
        or os.environ.get("AI_BASE_URL")
        or "https://api.deepseek.com/v1"
    ).rstrip("/")
    model = settings.get("ai_model") or os.environ.get("AI_MODEL") or "deepseek-chat"
    key = get_key("ai_api_key") or os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    return base, model, key


async def chat(message: str, *, thread_id: int | None = None) -> dict[str, Any]:
    base, model, key = _ai_config()
    if not key:
        # 无 Key 时走本地启发式，保证前端可用
        stats = await _tool_stats({"keyword": message})
        rec = await _tool_recommend({"keyword": message, "limit": 5})
        content = (
            "还没有配置 AI_API_KEY，先用本机样本做了粗判：\n"
            f"- 样本数 {stats.get('sample_n')}，中位 {stats.get('median')}，均值 {stats.get('mean')}\n"
            f"- 候选 {len(rec.get('items') or [])} 件（详见 refs）\n"
            "在设置里填入 OpenAI 兼容 Key 后可获得完整自然语言分析。"
        )
        thread = await AiThread.get_or_none(id=thread_id) if thread_id else None
        if thread is None:
            thread = await AiThread.create(title=message[:40] or "新对话")
        await AiMessage.create(thread=thread, role="user", content=message)
        refs = [item["item"] for item in rec.get("items") or [] if item.get("item")]
        await AiMessage.create(thread=thread, role="assistant", content=content, refs=refs)
        return {
            "thread_id": thread.id,
            "reply": content,
            "refs": refs,
            "stats": stats,
            "offline": True,
        }

    thread = await AiThread.get_or_none(id=thread_id) if thread_id else None
    if thread is None:
        thread = await AiThread.create(title=message[:40] or "新对话")
    await AiMessage.create(thread=thread, role="user", content=message)

    history = await AiMessage.filter(thread_id=thread.id).order_by("id")
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是闲鱼购物助手。用中文简短回答。"
                "价格判断必须基于工具返回的本机样本，并声明非全网官方行情。"
                "需要搜货、均价、推荐或起草私信时调用工具。"
                "不要假装已经发送私信。"
            ),
        }
    ]
    for row in history[-20:]:
        messages.append({"role": row.role, "content": row.content})

    refs: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=90) as client:
        for _ in range(4):
            res = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": messages,
                    "tools": TOOLS,
                    "tool_choice": "auto",
                },
            )
            if res.status_code >= 400:
                raise RuntimeError(f"AI 请求失败: {res.status_code} {res.text[:300]}")
            data = res.json()
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                reply = str(msg.get("content") or "").strip() or "（空回复）"
                await AiMessage.create(thread=thread, role="assistant", content=reply, refs=refs)
                return {"thread_id": thread.id, "reply": reply, "refs": refs, "offline": False}
            messages.append(msg)
            for call in tool_calls:
                fn = call.get("function") or {}
                name = fn.get("name") or ""
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                result = await run_tool(name, args)
                if name in {"search_items", "recommend"}:
                    items = result.get("items") or []
                    for entry in items:
                        item = entry.get("item") if isinstance(entry, dict) and "item" in entry else entry
                        if isinstance(item, dict):
                            refs.append(item)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": json.dumps(result, ensure_ascii=False)[:8000],
                    }
                )
    raise RuntimeError("AI 工具循环过多")
