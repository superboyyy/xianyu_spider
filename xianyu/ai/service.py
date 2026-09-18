"""AI 问询：多厂商 LLM + 本机工具。"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from xianyu.ai.providers import (
    LLMConfig,
    anthropic_headers,
    anthropic_to_openai_message,
    anthropic_url,
    openai_chat_url,
    openai_headers,
    openai_messages_to_anthropic,
    openai_tools_to_anthropic,
    resolve_config,
)
from xianyu.catalog import attach_saved_ids, product_to_public, public_from_raw
from xianyu.models import AiMessage, AiThread, PriceSnapshot, XianyuProduct
from xianyu.pricing import parse_price, summarize_prices
from xianyu.search import save_to_db, scrape_xianyu_http
from xianyu.search_query import SearchFilters

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
    weak_sample = int(stats.get("sample_n") or 0) < 5
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
        if weak_sample:
            score = min(score, 54)
            risks.append("样本少于 5，判断偏弱")
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
    return {
        "stats": stats,
        "items": scored[:limit],
        "disclaimer": "基于本机样本的启发式判断",
        "weak_sample": weak_sample,
    }


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


def _collect_refs(name: str, result: dict[str, Any], refs: list[dict[str, Any]]) -> None:
    if name not in {"search_items", "recommend"}:
        return
    for entry in result.get("items") or []:
        item = entry.get("item") if isinstance(entry, dict) and "item" in entry else entry
        if isinstance(item, dict):
            refs.append(item)


async def offline_reply(message: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    stats = await _tool_stats({"keyword": message})
    rec = await _tool_recommend({"keyword": message, "limit": 5})
    content = (
        "当前没有可用的云端模型，先用本机样本做了粗判：\n"
        f"- 样本数 {stats.get('sample_n')}，中位 {stats.get('median')}，均值 {stats.get('mean')}\n"
        f"- 候选 {len(rec.get('items') or [])} 件（详见右侧引用）\n"
        "样本不足时倾向「再看看」。在设置里选厂商并填 Key（Ollama 本地可不填）后可走完整对话。"
    )
    refs = [item["item"] for item in rec.get("items") or [] if item.get("item")]
    return content, refs, stats


async def _complete_openai(cfg: LLMConfig, messages: list[dict[str, Any]], *, use_tools: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": cfg.model, "messages": messages}
    if use_tools:
        payload["tools"] = TOOLS
        payload["tool_choice"] = "auto"
    async with httpx.AsyncClient(timeout=90) as client:
        res = await client.post(openai_chat_url(cfg), headers=openai_headers(cfg), json=payload)
        if res.status_code >= 400:
            raise RuntimeError(f"AI 请求失败: {res.status_code} {res.text[:300]}")
        data = res.json()
    choice = (data.get("choices") or [{}])[0]
    return choice.get("message") or {}


async def _complete_anthropic(cfg: LLMConfig, messages: list[dict[str, Any]], *, use_tools: bool) -> dict[str, Any]:
    system, converted = openai_messages_to_anthropic(messages)
    payload: dict[str, Any] = {
        "model": cfg.model,
        "max_tokens": 2048,
        "system": system,
        "messages": converted,
    }
    if use_tools:
        payload["tools"] = openai_tools_to_anthropic(TOOLS)
    async with httpx.AsyncClient(timeout=90) as client:
        res = await client.post(anthropic_url(cfg), headers=anthropic_headers(cfg), json=payload)
        if res.status_code >= 400:
            raise RuntimeError(f"AI 请求失败: {res.status_code} {res.text[:300]}")
        data = res.json()
    return anthropic_to_openai_message(data)


async def _complete(cfg: LLMConfig, messages: list[dict[str, Any]], *, use_tools: bool) -> dict[str, Any]:
    if cfg.protocol == "anthropic":
        return await _complete_anthropic(cfg, messages, use_tools=use_tools)
    return await _complete_openai(cfg, messages, use_tools=use_tools)


def _looks_like_tool_unsupported(exc: Exception) -> bool:
    text = str(exc).lower()
    needles = ("tool", "function calling", "tools", "tool_choice", "not support")
    return any(needle in text for needle in needles)


async def _run_tool_loop(cfg: LLMConfig, messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    refs: list[dict[str, Any]] = []
    use_tools = True
    for _ in range(4):
        try:
            msg = await _complete(cfg, messages, use_tools=use_tools)
        except RuntimeError as exc:
            if use_tools and _looks_like_tool_unsupported(exc):
                logger.info("当前模型不支持 tools，改走本机工具 + 纯文本: %s", exc)
                use_tools = False
                stats = await _tool_stats({"keyword": messages[-1].get("content") or ""})
                rec = await _tool_recommend({"keyword": messages[-1].get("content") or "", "limit": 5})
                _collect_refs("recommend", rec, refs)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "下面是本机工具结果，请用中文总结，并声明非全网官方行情：\n"
                            + json.dumps({"stats": stats, "recommend": rec}, ensure_ascii=False)[:8000]
                        ),
                    }
                )
                continue
            raise
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            reply = str(msg.get("content") or "").strip() or "（空回复）"
            return reply, refs
        messages.append(msg)
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            result = await run_tool(name, args)
            _collect_refs(name, result, refs)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": json.dumps(result, ensure_ascii=False)[:8000],
                }
            )
    raise RuntimeError("AI 工具循环过多")


async def chat(message: str, *, thread_id: int | None = None) -> dict[str, Any]:
    cfg = resolve_config()
    thread = await AiThread.get_or_none(id=thread_id) if thread_id else None
    if thread is None:
        thread = await AiThread.create(title=message[:40] or "新对话")
    await AiMessage.create(thread=thread, role="user", content=message)

    if not cfg.can_call:
        content, refs, stats = await offline_reply(message)
        await AiMessage.create(thread=thread, role="assistant", content=content, refs=refs)
        return {
            "thread_id": thread.id,
            "reply": content,
            "refs": refs,
            "stats": stats,
            "offline": True,
            "provider": cfg.provider_id,
            "provider_label": cfg.label,
        }

    history = await AiMessage.filter(thread_id=thread.id).order_by("id")
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是闲鱼购物助手。用中文简短回答。"
                "价格判断必须基于工具返回的本机样本，并声明非全网官方行情。"
                "需要搜货、均价、推荐或起草私信时调用工具。"
                "不要假装已经发送私信。自动回复目前只允许草稿。"
            ),
        }
    ]
    for row in history[-20:]:
        if row.role in {"user", "assistant"}:
            messages.append({"role": row.role, "content": row.content})

    try:
        reply, refs = await _run_tool_loop(cfg, messages)
    except Exception as exc:
        logger.exception("云端模型失败，回落到本机粗判")
        content, refs, stats = await offline_reply(message)
        content = f"云端模型调用失败（{exc}），改用本机粗判：\n" + content
        await AiMessage.create(thread=thread, role="assistant", content=content, refs=refs)
        return {
            "thread_id": thread.id,
            "reply": content,
            "refs": refs,
            "stats": stats,
            "offline": True,
            "provider": cfg.provider_id,
            "provider_label": cfg.label,
            "error": str(exc),
        }

    await AiMessage.create(thread=thread, role="assistant", content=reply, refs=refs)
    return {
        "thread_id": thread.id,
        "reply": reply,
        "refs": refs,
        "offline": False,
        "provider": cfg.provider_id,
        "provider_label": cfg.label,
    }
