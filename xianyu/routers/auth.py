from html import escape

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from xianyu.im_worker import im_service
from xianyu.mtop import (
    fetch_login_user,
    login_snapshot,
    login_with_cookie,
    logout,
    poll_qr_login,
    qr_continue_context,
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


@router.get("/qr/continue", summary="扫码后手机验证说明页", response_class=HTMLResponse)
async def auth_qr_continue(session_id: str = Query(..., description="start 接口返回的 session_id")):
    try:
        ctx = qr_continue_context(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(_continue_page_html(ctx))


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


def _continue_page_html(ctx: dict) -> str:
    verification_url = escape(str(ctx.get("verification_url") or ""))
    session_id = escape(str(ctx.get("session_id") or ""))
    logged_in = "已登录" if ctx.get("logged_in") else "未登录"
    user_id = escape(str(ctx.get("user_id") or "-"))
    verify_block = (
        f'<p><a href="{verification_url}" target="_blank" rel="noopener">打开闲鱼/淘宝验证页</a></p>'
        if verification_url
        else "<p>当前没有官方验证链接。如果手机上已经弹出验证，请在 App 里完成。</p>"
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>闲鱼扫码登录 · 手机验证</title>
  <style>
    body {{ font-family: sans-serif; max-width: 720px; margin: 32px auto; padding: 0 16px; line-height: 1.6; }}
    textarea {{ width: 100%; min-height: 140px; }}
    .ok {{ color: #0a7; }}
    .warn {{ color: #c40; }}
    code {{ background: #f4f4f4; padding: 0 4px; }}
  </style>
</head>
<body>
  <h1>扫码后需要手机验证</h1>
  <p>当前会话 <code>{session_id}</code>：<strong>{logged_in}</strong>，user_id={user_id}</p>
  <ol>
    <li>在闲鱼 App 里完成确认；如果弹出短信/人脸验证，在 <strong>手机上</strong> 做完。</li>
    <li>不要重新生成二维码，回到本页或继续轮询 <code>GET /auth/qr/status</code>。</li>
    <li>如果你是在电脑浏览器里打开了验证页：验证完成后的 Cookie 只在浏览器里，<strong>不会自动进本服务</strong>。请打开
      <a href="https://www.goofish.com/" target="_blank" rel="noopener">www.goofish.com</a>，
      按 F12 → Network/Application 复制完整 Cookie，粘贴到下面。</li>
  </ol>
  {verify_block}
  <form id="cookie-form">
    <p><label>粘贴 www.goofish.com 的完整 Cookie</label></p>
    <textarea name="cookie" placeholder="unb=...; cookie2=...; sgcookie=...; _m_h5_tk=..."></textarea>
    <p><button type="submit">导入 Cookie 并登录</button></p>
  </form>
  <pre id="result"></pre>
  <script>
    const sessionId = {session_id!r};
    const form = document.getElementById("cookie-form");
    const result = document.getElementById("result");
    async function refreshStatus() {{
      const res = await fetch("/auth/qr/status?session_id=" + encodeURIComponent(sessionId));
      const data = await res.json();
      if (data.logged_in) {{
        result.className = "ok";
        result.textContent = "登录成功: " + JSON.stringify(data, null, 2);
      }}
    }}
    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      const cookie = form.cookie.value;
      const res = await fetch("/auth/cookie", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ cookie }}),
      }});
      const data = await res.json();
      result.className = res.ok ? "ok" : "warn";
      result.textContent = JSON.stringify(data, null, 2);
    }});
    refreshStatus();
    setInterval(refreshStatus, 3000);
  </script>
</body>
</html>
"""
