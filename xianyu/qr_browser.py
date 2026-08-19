"""用本机 Chromium 完成扫码后的手机验证，并把 Cookie 自动写回服务。"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from xianyu.protocol import (
    cookie_user_id,
    cookies_from_query_url,
    has_login_cookies,
    has_official_session_cookies,
)
from xianyu import mtop

_jobs: dict[str, dict[str, Any]] = {}


def import_playwright_cookies(cookies: list[dict]) -> None:
    """把浏览器 Cookie 写进 httpx，并提升到 .goofish.com。"""
    pairs: dict[str, str] = {}
    for item in cookies or []:
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        if name and value:
            pairs[name] = value
    if pairs:
        mtop.apply_cookies(pairs)
        mtop._promote_cookies_to_goofish()


def export_playwright_cookies() -> list[dict]:
    """把当前 httpx Cookie 转成 Playwright 格式，同时种到 www / passport。"""
    items: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for cookie in mtop.client.cookies.jar:
        if not cookie.name or cookie.value is None:
            continue
        for url in ("https://www.goofish.com/", "https://passport.goofish.com/"):
            key = (cookie.name, url)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "url": url,
                    "path": cookie.path or "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "Lax",
                }
            )
    return items


def browser_job(session_id: str) -> dict:
    job = _jobs.get(session_id) or {}
    return {
        "status": job.get("status") or "idle",
        "hint": job.get("hint") or "",
        "error": job.get("error") or "",
    }


async def start_browser_verify(session_id: str) -> dict:
    session = mtop._qr_sessions.get(session_id)
    if not session:
        raise KeyError("二维码会话不存在或已过期，请重新生成")
    snapshot = mtop.login_snapshot()
    if snapshot.get("logged_in"):
        return {
            "ok": True,
            "logged_in": True,
            "status": "done",
            "hint": "已经登录，不用再验证。",
        }
    current = _jobs.get(session_id) or {}
    if current.get("status") == "running":
        return {
            "ok": True,
            "logged_in": False,
            "status": "running",
            "hint": current.get("hint") or "浏览器已打开，请在弹出的窗口里完成验证。",
        }
    _jobs[session_id] = {
        "status": "running",
        "hint": "正在打开本机浏览器，请在弹出的窗口里完成验证，不用粘贴 Cookie。",
        "error": "",
    }
    asyncio.create_task(_guarded_run(session_id))
    return {
        "ok": True,
        "logged_in": False,
        "status": "running",
        "hint": "已尝试打开本机浏览器。在窗口里完成验证即可，Cookie 会自动导入。",
    }


async def _guarded_run(session_id: str) -> None:
    try:
        await _run_browser_verify(session_id)
        snapshot = mtop.login_snapshot()
        if snapshot.get("logged_in"):
            _jobs[session_id] = {
                "status": "done",
                "hint": "验证完成，已自动登录。",
                "error": "",
            }
        else:
            job = _jobs.get(session_id) or {}
            if job.get("status") != "error":
                _jobs[session_id] = {
                    "status": "error",
                    "hint": "浏览器已关闭，但仍未登录。请在闲鱼 App 里完成验证后等待本页自动刷新。",
                    "error": job.get("error") or "",
                }
    except Exception as exc:
        _jobs[session_id] = {
            "status": "error",
            "hint": str(exc),
            "error": str(exc),
        }


async def _try_finish_login(session_id: str) -> bool:
    session = mtop._qr_sessions.get(session_id)
    if not session:
        return bool(mtop.login_snapshot().get("logged_in"))
    completed = await mtop._complete_qr_login(session, session_id)
    if completed:
        return True
    mtop.persist_login()
    return bool(mtop.login_snapshot().get("logged_in"))


def _logged_in_from_cookies() -> bool:
    cookies = mtop.current_cookies()
    return bool(cookie_user_id(cookies) or has_login_cookies(cookies))


async def complete_browser_verify(session_id: str, *, timeout: int = 180) -> dict:
    """同步走完核身窗口：给 CLI 在扫码后需要拍脸时调用。"""
    await _run_browser_verify(session_id, timeout=timeout)
    snapshot = mtop.login_snapshot()
    return snapshot | {"ok": bool(snapshot.get("logged_in"))}


async def _run_browser_verify(session_id: str, *, timeout: int = 180) -> None:
    import shutil
    import tempfile
    import time

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "未安装 playwright。请执行: pip install -r requirements.txt && playwright install chromium"
        ) from exc

    session = mtop._qr_sessions.get(session_id) or {}
    verify_url = str(session.get("verification_url") or "").strip()
    start_url = verify_url or "https://www.goofish.com/"
    profile_dir = tempfile.mkdtemp(prefix="xianyu-verify-")
    try:
        async with async_playwright() as playwright:
            context = await _open_login_context(playwright, profile_dir)
            exported = export_playwright_cookies()
            if exported:
                try:
                    await context.add_cookies(exported)
                except Exception:
                    pass
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                await page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
            except Exception:
                pass
            try:
                await page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                try:
                    await page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
                except Exception as exc:
                    await context.close()
                    raise RuntimeError(f"打开验证页失败: {exc}") from exc

            deadline = time.monotonic() + max(int(timeout), 30)
            while time.monotonic() < deadline:
                try:
                    browser_cookies = await context.cookies()
                except Exception:
                    browser_cookies = []
                import_playwright_cookies(browser_cookies)
                try:
                    apply_from_url = cookies_from_query_url(page.url)
                    if apply_from_url:
                        mtop.apply_cookies(apply_from_url)
                        mtop._promote_cookies_to_goofish()
                except Exception:
                    pass
                if _cookie_list_logged_in(browser_cookies) or await _try_finish_login(session_id):
                    break
                if session_id not in mtop._qr_sessions and mtop.login_snapshot().get("logged_in"):
                    break
                await asyncio.sleep(1)

            try:
                leftover = await context.cookies()
                import_playwright_cookies(leftover)
            except Exception:
                pass
            await _try_finish_login(session_id)
            try:
                await context.close()
            except Exception:
                pass
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


OFFICIAL_LOGIN_URL = "https://www.goofish.com/login"


def _pairs_from_cookie_list(cookies: list[dict]) -> dict[str, str]:
    return {
        str(item.get("name") or ""): str(item.get("value") or "")
        for item in cookies or []
        if item.get("name") and item.get("value")
    }


def _cookie_list_logged_in(cookies: list[dict]) -> bool:
    """官方页登录成功判定：与 goofish-cli 一样，三个 Cookie 必须齐全。"""
    return has_official_session_cookies(_pairs_from_cookie_list(cookies))


async def _find_passport_frame(page: Any, timeout_s: float = 20) -> Any:
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        for frame in getattr(page, "frames", []) or []:
            if "passport" in (getattr(frame, "url", "") or ""):
                return frame
        await asyncio.sleep(0.5)
    return None


async def _wait_for_qr(page: Any, timeout_ms: int = 15000) -> bool:
    """等 passport iframe 里的扫码区出来。找不到也不当失败，继续轮询 Cookie。"""
    frame = await _find_passport_frame(page)
    if not frame:
        return False
    try:
        await frame.wait_for_selector(".qrcode-login", timeout=timeout_ms)
        return True
    except Exception:
        return False


async def _open_login_context(playwright: Any, profile_dir: str):
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-default-browser-check",
        "--no-first-run",
    ]
    kwargs = {
        "user_data_dir": profile_dir,
        "headless": False,
        "viewport": {"width": 1440, "height": 900},
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "args": args,
    }
    try:
        return await playwright.chromium.launch_persistent_context(channel="chrome", **kwargs)
    except Exception:
        pass
    try:
        return await playwright.chromium.launch_persistent_context(**kwargs)
    except Exception as exc:
        raise RuntimeError(
            "无法打开本机浏览器。请在有桌面的电脑上运行；优先用已安装的 Chrome，"
            "或先执行 pip install -r requirements.txt && playwright install chromium。"
            "也可以改用：python spider.py login --cookie"
        ) from exc


async def login_via_official_page(*, timeout: int = 180) -> dict:
    """打开闲鱼官方登录页扫码。拍脸也在这个窗口完成，Cookie 直接写回。

    对齐 fancyboi999/goofish-cli：
    1. 干净临时 Chrome profile（不灌已有 Cookie，否则会走「快速进入」看不到码）
    2. 打开 https://www.goofish.com/login
    3. 等 passport iframe 里的二维码
    4. 轮询 Cookie，直到 _m_h5_tk / unb / cookie2 齐全
    """
    import shutil
    import tempfile
    import time

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "未安装 playwright。请执行: pip install -r requirements.txt && playwright install chromium"
        ) from exc

    profile_dir = tempfile.mkdtemp(prefix="xianyu-login-")
    last_cookies: list[dict] = []
    try:
        async with async_playwright() as playwright:
            context = await _open_login_context(playwright, profile_dir)
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                await page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
            except Exception:
                pass
            try:
                await page.goto(OFFICIAL_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            except Exception as exc:
                try:
                    await context.close()
                except Exception:
                    pass
                raise RuntimeError(f"打开闲鱼登录页失败: {exc}") from exc
            await asyncio.sleep(1.5)
            await _wait_for_qr(page)

            deadline = time.monotonic() + max(int(timeout), 30)
            while time.monotonic() < deadline:
                try:
                    last_cookies = await context.cookies()
                except Exception:
                    last_cookies = []
                import_playwright_cookies(last_cookies)
                if _cookie_list_logged_in(last_cookies):
                    break
                await asyncio.sleep(1)

            try:
                leftover = await context.cookies()
                if leftover:
                    last_cookies = leftover
                import_playwright_cookies(last_cookies)
            except Exception:
                pass
            try:
                await context.close()
            except Exception:
                pass
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    mtop.persist_login()
    snapshot = mtop.login_snapshot()
    cookies = mtop.current_cookies()
    if _cookie_list_logged_in(last_cookies) or has_official_session_cookies(cookies):
        try:
            await mtop.init_h5tk()
            user = await mtop.fetch_login_user()
            snapshot = mtop.login_snapshot() | {"user": user}
        except Exception:
            pass
        return snapshot | {"ok": True, "hint": "浏览器扫码登录成功。"}
    return {
        "ok": False,
        "logged_in": False,
        "hint": (
            "浏览器窗口已关闭，仍未拿到完整登录 Cookie（需要 unb、cookie2、_m_h5_tk）。"
            "请用闲鱼 App 扫官方登录页里的码并确认；拍脸也在同一窗口完成。"
            "或先在系统 Chrome 登录 www.goofish.com，再运行 python spider.py login --cookie。"
        ),
    }
