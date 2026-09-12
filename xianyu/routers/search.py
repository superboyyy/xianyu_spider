import traceback

from fastapi import APIRouter, HTTPException

from xianyu.catalog import attach_saved_ids, public_from_raw
from xianyu.mtop import LOGIN_EXPIRED_HINT, probe_login
from xianyu.schemas import SearchBody
from xianyu.search import save_to_db, scrape_xianyu_http

router = APIRouter()


@router.post(
    "/search/",
    summary="商品搜索接口",
    description="按关键词抓取商品。可指定排序、价格区间、地区；返回是否登录态。登录失效时仍按未登录继续。",
)
async def search_items(body: SearchBody):
    try:
        snapshot = await probe_login()
        filters = body.filters()
        data_list = await scrape_xianyu_http(body.keyword, body.max_pages, filters=filters)
        new_count, new_ids = (0, [])
        items = [public_from_raw(item) for item in data_list]
        if data_list:
            new_count, new_ids = await save_to_db(data_list)
            items = await attach_saved_ids(items, new_ids)
        payload = {
            "status": "success",
            "keyword": body.keyword,
            "logged_in": bool(snapshot.get("logged_in")),
            "user_id": snapshot.get("user_id") or "",
            "filters": filters.public_dict(),
            "total_results": len(data_list),
            "new_records": new_count,
            "new_record_ids": new_ids,
            "items": items,
        }
        if snapshot.get("login_expired"):
            payload["login_expired"] = True
            payload["hint"] = snapshot.get("hint") or LOGIN_EXPIRED_HINT
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"爬取失败: {exc}") from exc
