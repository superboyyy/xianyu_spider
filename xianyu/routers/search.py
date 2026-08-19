import traceback

from fastapi import APIRouter, HTTPException

from xianyu.search import save_to_db, scrape_xianyu_http

router = APIRouter()


@router.post(
    "/search/",
    summary="商品搜索接口",
    description="接收搜索关键词和页数，返回爬取结果数量、新增记录数量及新增记录的id列表",
)
async def search_items(keyword: str, max_pages: int = 1):
    try:
        data_list = await scrape_xianyu_http(keyword, max_pages)
        new_count, new_ids = (0, [])
        if data_list:
            new_count, new_ids = await save_to_db(data_list)
        return {
            "status": "success",
            "keyword": keyword,
            "total_results": len(data_list),
            "new_records": new_count,
            "new_record_ids": new_ids,
        }
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"爬取失败: {exc}") from exc
