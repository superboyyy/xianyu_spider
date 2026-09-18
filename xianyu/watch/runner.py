"""盯盘执行：搜索、入库、价格快照、触发通知。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from xianyu.catalog import public_from_raw
from xianyu.models import PriceSnapshot, Watch, WatchRun
from xianyu.notify.service import dispatch_notify, fingerprint
from xianyu.pricing import parse_price, summarize_prices
from xianyu.search import save_to_db, scrape_xianyu_http
from xianyu.search_query import SearchFilters

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def watch_filters(watch: Watch) -> SearchFilters:
    return SearchFilters(
        sort=watch.sort or "newest",
        min_price=watch.min_price,
        max_price=watch.max_price,
        province=watch.province,
        city=watch.city,
        publish_days=watch.publish_days,
    )


async def record_snapshots(
    *,
    watch: Watch,
    items: list[dict[str, Any]],
) -> list[float]:
    values: list[float] = []
    for item in items:
        price_text = str(item.get("price") or "")
        value = parse_price(price_text)
        if value is not None:
            values.append(value)
        await PriceSnapshot.create(
            keyword=watch.keyword,
            product_id=item.get("id"),
            item_id=str(item.get("item_id") or ""),
            link_hash="",
            title=str(item.get("title") or "")[:255],
            price_text=price_text,
            price_value=value,
            city=watch.city,
            watch_id=watch.id,
        )
    return values


async def evaluate_triggers(
    watch: Watch,
    *,
    items: list[dict[str, Any]],
    new_ids: list[int],
    price_values: list[float],
) -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []
    stats = summarize_prices(price_values)
    new_set = set(new_ids)

    if watch.notify_new:
        for item in items:
            if item.get("id") not in new_set:
                continue
            fp = fingerprint("new_listing", watch.id, item.get("item_id") or item.get("id"))
            title = f"上新 · {watch.name or watch.keyword}"
            body = f"{item.get('title')} · {item.get('price')}"
            results = await dispatch_notify(
                event_type="new_listing",
                title=title,
                body=body,
                fingerprint_key=fp,
                payload={"watch_id": watch.id, "item": item},
            )
            triggered.append({"type": "new_listing", "item": item, "notify": results})

    if watch.notify_below_target and watch.target_price is not None:
        for item in items:
            value = parse_price(item.get("price"))
            if value is None or value > float(watch.target_price):
                continue
            fp = fingerprint("below_target", watch.id, item.get("item_id") or item.get("id"), value)
            title = f"低价 · {watch.name or watch.keyword}"
            body = f"{item.get('title')} · {item.get('price')}（目标 ≤ {watch.target_price:g}）"
            results = await dispatch_notify(
                event_type="below_target",
                title=title,
                body=body,
                fingerprint_key=fp,
                payload={"watch_id": watch.id, "item": item, "target": watch.target_price},
            )
            triggered.append({"type": "below_target", "item": item, "notify": results})

    if watch.notify_below_median_pct is not None and stats.get("median"):
        median = float(stats["median"])
        threshold = median * (1 - float(watch.notify_below_median_pct) / 100.0)
        for item in items:
            value = parse_price(item.get("price"))
            if value is None or value > threshold:
                continue
            fp = fingerprint(
                "below_median_pct",
                watch.id,
                item.get("item_id") or item.get("id"),
                round(value, 2),
            )
            title = f"低于中位 · {watch.name or watch.keyword}"
            body = (
                f"{item.get('title')} · {item.get('price')} "
                f"（中位 {median:g}，阈值 {watch.notify_below_median_pct:g}%）"
            )
            results = await dispatch_notify(
                event_type="below_median_pct",
                title=title,
                body=body,
                fingerprint_key=fp,
                payload={"watch_id": watch.id, "item": item, "stats": stats},
            )
            triggered.append({"type": "below_median_pct", "item": item, "notify": results})

    return triggered


async def run_watch(watch_id: int) -> dict[str, Any]:
    watch = await Watch.get_or_none(id=watch_id)
    if watch is None:
        raise KeyError("盯盘任务不存在")
    try:
        from xianyu.mtop import probe_login

        try:
            snapshot = await probe_login()
        except Exception:
            snapshot = {}
        if snapshot.get("login_expired"):
            await dispatch_notify(
                event_type="login_expired",
                title="登录失效",
                body="盯盘仍按未登录继续搜，请重新扫码登录。",
                fingerprint_key=fingerprint("login_expired"),
                dedupe_hours=6,
            )
        filters = watch_filters(watch)
        raw = await scrape_xianyu_http(watch.keyword, watch.max_pages or 1, filters=filters)
        new_count, new_ids = (0, [])
        items = [public_from_raw(item) for item in raw]
        if raw:
            new_count, new_ids = await save_to_db(raw)
            from xianyu.catalog import attach_saved_ids

            items = await attach_saved_ids(items, new_ids)
        price_values = await record_snapshots(watch=watch, items=items)
        triggered = await evaluate_triggers(
            watch, items=items, new_ids=new_ids, price_values=price_values
        )
        stats = summarize_prices(price_values)
        run = await WatchRun.create(
            watch=watch,
            status="ok",
            total_results=len(items),
            new_records=new_count,
            min_price=stats.get("min"),
            triggered=[{"type": t["type"], "item_id": (t["item"] or {}).get("id")} for t in triggered],
        )
        watch.last_run_at = _utcnow()
        watch.last_error = ""
        await watch.save()
        return {
            "watch_id": watch.id,
            "run_id": run.id,
            "total_results": len(items),
            "new_records": new_count,
            "stats": stats,
            "triggered": triggered,
            "items": items[:30],
        }
    except Exception as exc:
        logger.exception("盯盘失败 watch=%s", watch_id)
        await WatchRun.create(
            watch=watch,
            status="error",
            error=str(exc),
            triggered=[],
        )
        watch.last_run_at = _utcnow()
        watch.last_error = str(exc)
        await watch.save()
        raise
