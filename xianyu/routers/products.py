from fastapi import APIRouter, HTTPException, Query

from xianyu.catalog import product_to_public
from xianyu.models import XianyuProduct

router = APIRouter(tags=["products"])


@router.get("/products", summary="本地货架")
async def list_products(
    q: str | None = Query(None, description="按标题筛选"),
    limit: int = Query(40, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = XianyuProduct.all().order_by("-id")
    keyword = (q or "").strip()
    if keyword:
        query = query.filter(title__icontains=keyword)
    total = await query.count()
    rows = await query.offset(offset).limit(limit)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [product_to_public(row) for row in rows],
    }


@router.get("/products/{product_id}", summary="货架单条")
async def get_product(product_id: int):
    row = await XianyuProduct.get_or_none(id=product_id)
    if row is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product_to_public(row)
