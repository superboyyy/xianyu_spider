from fastapi import APIRouter, HTTPException, Query

from xianyu.im_worker import im_service
from xianyu.mtop import (
    fetch_login_user,
    login_snapshot,
    login_with_cookie,
    logout,
    poll_qr_login,
    start_qr_login,
)
from xianyu.schemas import CookieLoginBody

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/cookie", summary="Cookie 登录")
async def auth_cookie(body: CookieLoginBody):
    try:
        return await login_with_cookie(body.cookie)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"登录失败: {exc}") from exc


@router.post("/qr/start", summary="生成闲鱼扫码登录二维码")
async def auth_qr_start():
    try:
        return await start_qr_login()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"二维码生成失败: {exc}") from exc


@router.get("/qr/status", summary="查询扫码登录状态")
async def auth_qr_status(session_id: str = Query(..., description="start 接口返回的 session_id")):
    try:
        return await poll_qr_login(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"查询扫码状态失败: {exc}") from exc


@router.get("/status", summary="当前登录态")
async def auth_status():
    snapshot = login_snapshot()
    if snapshot.get("logged_in"):
        try:
            snapshot["user"] = await fetch_login_user()
        except Exception as exc:
            snapshot["warning"] = str(exc)
    return snapshot


@router.post("/logout", summary="退出登录")
async def auth_logout():
    await im_service.stop()
    logout()
    return {"ok": True}
