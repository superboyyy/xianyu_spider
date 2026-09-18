from fastapi import APIRouter, HTTPException, Query

from xianyu.catalog import product_to_public
from xianyu.models import PriceSnapshot, XianyuProduct
from xianyu.pricing import parse_price, summarize_prices

router = APIRouter(tags=["products"])


@router.get("/products", summary="本地货架")
async def list_products(
    q: str | None = Query(None, description="按标题筛选"),
    limit: int = Query(40, ge=1, le=200),
    offset: int = Query(0, ge=0),
    stats: bool = Query(False, description="附带价格样本统计"),
):
    query = XianyuProduct.all().order_by("-id")
    keyword = (q or "").strip()
    if keyword:
        query = query.filter(title__icontains=keyword)
    total = await query.count()
    rows = await query.offset(offset).limit(limit)
    payload = {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [product_to_public(row) for row in rows],
    }
    if stats:
        values = [parse_price(row.price) for row in rows]
        payload["stats"] = summarize_prices([v for v in values if v is not None])
    return payload


@router.get("/products/stats", summary="价格样本统计")
async def product_stats(
    q: str = Query(..., min_length=1, description="关键词"),
):
    keyword = q.strip()
    rows = await XianyuProduct.filter(title__icontains=keyword).limit(300)
    values = [parse_price(row.price) for row in rows]
    snaps = await PriceSnapshot.filter(keyword__icontains=keyword).limit(300)
    snap_vals = [s.price_value for s in snaps if s.price_value is not None]
    merged = [v for v in values if v is not None] + snap_vals
    return {
        "keyword": keyword,
        "disclaimer": "基于本机货架与盯盘快照，不是全网官方行情",
        **summarize_prices(merged),
    }


@router.get("/products/{product_id}", summary="货架单条")
async def get_product(product_id: int):
    row = await XianyuProduct.get_or_none(id=product_id)
    if row is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product_to_public(row)
