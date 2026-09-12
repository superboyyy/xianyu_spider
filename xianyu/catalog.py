"""商品对外字段：搜索结果和货架共用同一份结构。"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from xianyu.models import XianyuProduct


def link_unique_key(link: str) -> str:
    parts = (link or "").split("&", 1)
    return parts[0] if len(parts) >= 2 else (link or "")


def link_hash(link: str) -> str:
    return hashlib.md5(link_unique_key(link).encode("utf-8")).hexdigest()


def item_id_from_link(link: str) -> str:
    text = (link or "").strip()
    if not text:
        return ""
    parsed = urlparse(text.replace("fleamarket://", "https://www.goofish.com/"))
    query = parse_qs(parsed.query)
    for key in ("id", "itemId", "item_id"):
        values = query.get(key) or []
        if values and values[0]:
            return str(values[0])
    for part in parsed.path.rstrip("/").split("/"):
        if part.isdigit():
            return part
    return ""


def _text(item: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in {"暂无", "未知标题", "未知时间"}:
            return text
    return default


def public_from_raw(
    item: dict[str, Any],
    *,
    product_id: Optional[int] = None,
    is_new: bool = False,
) -> dict[str, Any]:
    link = _text(item, "商品链接", "link")
    publish = item.get("发布时间") or item.get("publish_time") or ""
    if isinstance(publish, datetime):
        publish = publish.strftime("%Y-%m-%d %H:%M")
    publish_text = str(publish).strip()
    if publish_text in {"", "未知时间"}:
        publish_text = ""
    return {
        "id": product_id,
        "item_id": _text(item, "item_id") or item_id_from_link(link),
        "title": _text(item, "商品标题", "title"),
        "price": _text(item, "当前售价", "price"),
        "area": _text(item, "发货地区", "area"),
        "seller": _text(item, "卖家昵称", "seller"),
        "seller_id": _text(item, "seller_id"),
        "link": link,
        "image_url": _text(item, "商品图片链接", "image_url"),
        "publish_time": publish_text or None,
        "is_new": bool(is_new),
    }


def product_to_public(
    row: XianyuProduct,
    *,
    is_new: bool = False,
    seller_id: str = "",
) -> dict[str, Any]:
    publish = row.publish_time.strftime("%Y-%m-%d %H:%M") if row.publish_time else None
    return {
        "id": row.id,
        "item_id": item_id_from_link(row.link),
        "title": row.title,
        "price": row.price,
        "area": row.area,
        "seller": row.seller,
        "seller_id": seller_id,
        "link": row.link,
        "image_url": row.image_url,
        "publish_time": publish,
        "is_new": bool(is_new),
    }


async def attach_saved_ids(items: list[dict[str, Any]], new_ids: list[int]) -> list[dict[str, Any]]:
    hashes = [link_hash(item["link"]) for item in items if item.get("link")]
    if not hashes:
        return items
    rows = await XianyuProduct.filter(link_hash__in=hashes)
    by_hash = {row.link_hash: row for row in rows}
    marked = set(new_ids)
    attached: list[dict[str, Any]] = []
    for item in items:
        row = by_hash.get(link_hash(item["link"])) if item.get("link") else None
        if row is None:
            attached.append(item)
            continue
        merged = dict(item)
        merged["id"] = row.id
        merged["is_new"] = row.id in marked
        if not merged.get("item_id"):
            merged["item_id"] = item_id_from_link(row.link)
        attached.append(merged)
    return attached
