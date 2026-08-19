import json
from html import escape

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from xianyu.im_worker import im_service
from xianyu import mtop as mtop_mod
from xianyu.mtop import (
    fetch_login_user,
    login_snapshot,
    login_with_cookie,
    logout,
    poll_qr_login,
    qr_continue_context,
    qr_text_for_session,
    start_qr_login,
)
from xianyu.qr_browser import browser_job, start_browser_verify
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


@router.get("/qr/text", summary="当前登录/验证二维码（终端文本）")
async def auth_qr_text(session_id: str = Query(..., description="start 接口返回的 session_id")):
    try:
        return PlainTextResponse(qr_text_for_session(session_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/qr/continue", summary="扫码后手机验证说明页", response_class=HTMLResponse)
async def auth_qr_continue(session_id: str = Query(..., description="start 接口返回的 session_id")):
    try:
        ctx = qr_continue_context(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(_continue_page_html(ctx))


@router.post("/qr/browser", summary="打开本机浏览器完成验证并自动导入 Cookie")
async def auth_qr_browser(session_id: str = Query(..., description="start 接口返回的 session_id")):
    try:
        return await start_browser_verify(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/qr/browser", summary="本机浏览器验证进度")
async def auth_qr_browser_status(session_id: str = Query(..., description="start 接口返回的 session_id")):
    if session_id not in mtop_mod._qr_sessions:
        raise HTTPException(status_code=404, detail="二维码会话不存在或已过期，请重新生成")
    return browser_job(session_id)


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
    session_js = json.dumps(str(ctx.get("session_id") or ""))
    logged_in = "已登录" if ctx.get("logged_in") else "未登录"
    user_id = escape(str(ctx.get("user_id") or "-"))
    face_verify = bool(ctx.get("face_verify"))
    qr_b64 = str(ctx.get("verification_qr_image_base64") or "")
    if face_verify:
        qr_block = f"""
  <h1>这是「拍摄脸部」核身，不要扫链接码</h1>
  <p class="left">你扫出来的页面里已经有官方二维码。再用闲鱼去扫「验证页链接」会套娃，手机上还是同一页。</p>
  <ol class="left">
    <li>点下面链接，用<strong>系统默认浏览器</strong>打开官方验证页（不必用 Playwright）。</li>
    <li>用闲鱼 App 扫<strong>浏览器里</strong>「拍摄脸部」那个码（不要用系统相机）。</li>
    <li>按提示拍脸。拍完不要关页面，等它自动跳转；本服务会继续换登录态。</li>
  </ol>
  <p>
    <a href="{verification_url or '#'}" target="_blank" rel="noopener">用默认浏览器打开官方验证页</a>
  </p>
"""
    elif qr_b64:
        qr_block = f'''
  <h1>用闲鱼 App 扫这个验证码</h1>
  <p><img class="qr" alt="验证二维码" src="data:image/png;base64,{qr_b64}" /></p>
  <p class="left">打开<strong>闲鱼 App → 扫一扫</strong>扫描上方二维码（不要用系统相机）。</p>
  <p><button id="open-browser" type="button">打开本机浏览器完成验证</button></p>
'''
    else:
        qr_block = """
  <h1>手机验证</h1>
  <p>还没有验证链接。如果手机上已经弹出验证，直接在闲鱼 App 里完成即可。</p>
  <p><button id="open-browser" type="button">打开本机浏览器完成验证</button></p>
"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>闲鱼扫码登录 · 手机验证</title>
  <style>
    body {{ font-family: sans-serif; max-width: 720px; margin: 32px auto; padding: 0 16px; line-height: 1.6; text-align: center; }}
    .qr {{ width: 240px; height: 240px; background: #fff; padding: 8px; }}
    textarea {{ width: 100%; min-height: 120px; }}
    button {{ font-size: 16px; padding: 8px 16px; }}
    .ok {{ color: #0a7; }}
    .warn {{ color: #c40; }}
    code {{ background: #f4f4f4; padding: 0 4px; }}
    details {{ margin-top: 24px; text-align: left; }}
    .left {{ text-align: left; }}
  </style>
</head>
<body>
  <p>当前会话 <code>{session_id}</code>：<strong id="login-state">{logged_in}</strong>，user_id={user_id}</p>
  {qr_block}
  <p class="left">完成后本页会自动登录，不用粘贴 Cookie，也不要重新生成登录二维码。</p>
  <pre id="result">等待验证...</pre>
  <details>
    <summary>扫不了？其它方式</summary>
    <p>验证链接：<code>{verification_url or "无"}</code></p>
    <form id="cookie-form">
      <p><label>粘贴 www.goofish.com 的完整 Cookie</label></p>
      <textarea name="cookie" placeholder="unb=...; cookie2=...; sgcookie=...; _m_h5_tk=..."></textarea>
      <p><button type="submit">导入 Cookie 并登录</button></p>
    </form>
  </details>
  <script>
    const sessionId = {session_js};
    const form = document.getElementById("cookie-form");
    const result = document.getElementById("result");
    const loginState = document.getElementById("login-state");
    const openBtn = document.getElementById("open-browser");
    async function refreshStatus() {{
      const res = await fetch("/auth/qr/status?session_id=" + encodeURIComponent(sessionId));
      const data = await res.json();
      if (data.logged_in) {{
        loginState.textContent = "已登录";
        result.className = "ok";
        result.textContent = "登录成功: " + JSON.stringify(data, null, 2);
      }}
    }}
    if (openBtn) {{
      openBtn.addEventListener("click", async () => {{
        openBtn.disabled = true;
        result.textContent = "正在打开本机浏览器...";
        const res = await fetch("/auth/qr/browser?session_id=" + encodeURIComponent(sessionId), {{ method: "POST" }});
        const data = await res.json();
        result.className = res.ok ? "ok" : "warn";
        result.textContent = data.hint || JSON.stringify(data, null, 2);
        openBtn.disabled = false;
      }});
    }}
    if (form) {{
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
    }}
    refreshStatus();
    setInterval(refreshStatus, 2000);
  </script>
</body>
</html>
"""
