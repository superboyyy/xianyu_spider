from fastapi import APIRouter, HTTPException

from xianyu.models import Watch, WatchRun
from xianyu.schemas import WatchBody, watch_to_dict
from xianyu.watch.runner import run_watch
from xianyu.watch.scheduler import scheduler

router = APIRouter(prefix="/watches", tags=["watches"])


@router.get("")
async def list_watches():
    rows = await Watch.all().order_by("-id")
    return {"items": [watch_to_dict(row) for row in rows], "scheduler": scheduler.status()}


@router.post("")
async def create_watch(body: WatchBody):
    row = await Watch.create(**body.model_dump())
    return watch_to_dict(row)


@router.get("/{watch_id}")
async def get_watch(watch_id: int):
    row = await Watch.get_or_none(id=watch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="盯盘不存在")
    runs = await WatchRun.filter(watch_id=watch_id).order_by("-id").limit(20)
    return {
        **watch_to_dict(row),
        "runs": [
            {
                "id": run.id,
                "status": run.status,
                "total_results": run.total_results,
                "new_records": run.new_records,
                "min_price": run.min_price,
                "triggered": run.triggered,
                "error": run.error,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
            for run in runs
        ],
    }


@router.put("/{watch_id}")
async def update_watch(watch_id: int, body: WatchBody):
    row = await Watch.get_or_none(id=watch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="盯盘不存在")
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    await row.save()
    return watch_to_dict(row)


@router.delete("/{watch_id}")
async def delete_watch(watch_id: int):
    row = await Watch.get_or_none(id=watch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="盯盘不存在")
    await row.delete()
    return {"ok": True}


@router.post("/{watch_id}/run")
async def run_watch_now(watch_id: int):
    try:
        return await run_watch(watch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"盯盘执行失败: {exc}") from exc
