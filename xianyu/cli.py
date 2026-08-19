"""命令行扫码登录：在终端打印二维码并轮询直到登录成功。"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from typing import Any, Optional

from xianyu.protocol import qr_ascii

Printer = Callable[..., None]


def _emit(printer: Printer, *args: Any, **kwargs: Any) -> None:
    printer(*args, **kwargs)


def _open_default_browser(url: str) -> bool:
    """用系统默认浏览器打开验证页，不依赖 Playwright。"""
    text = (url or "").strip()
    if not text:
        return False
    try:
        import webbrowser

        return bool(webbrowser.open(text, new=2))
    except Exception:
        return False


def _stdin_is_interactive() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False


async def _read_stdin_line() -> str:
    return await asyncio.to_thread(sys.stdin.readline)


def _still_verifying(status: dict[str, Any], kind: str) -> bool:
    return bool(
        kind == "verification_required"
        or status.get("verification_pending")
        or status.get("face_verify")
        or status.get("verification_url")
    )


async def run_login(
    *,
    mode: str = "qr",
    cookie: str = "",
    poll_interval: float = 2.0,
    timeout: int = 180,
    printer: Optional[Printer] = None,
) -> int:
    """默认终端出登录码；需要拍脸时再开 Playwright。也支持 Cookie 或直接开官方登录页。"""
    print_fn: Printer = printer or print
    from xianyu.mtop import init, login_snapshot

    await init()
    snapshot = login_snapshot()
    if snapshot.get("logged_in"):
        _emit(print_fn, f"已经登录，user_id={snapshot.get('user_id') or '-'}")
        return 0

    kind = (mode or "qr").strip().lower()
    if kind == "cookie":
        return await _run_cookie_login(cookie=cookie, printer=print_fn)
    if kind == "browser":
        return await _run_browser_login(timeout=timeout, printer=print_fn)
    return await run_qr_login(poll_interval=poll_interval, timeout=timeout, printer=print_fn)


async def _run_browser_login(*, timeout: int, printer: Printer) -> int:
    _emit(printer, "将打开闲鱼官方登录页。请用闲鱼 App 扫浏览器里的码，并在手机上确认。")
    _emit(printer, "若弹出拍脸，在同一个浏览器窗口完成。不要去粘贴 ivCheckLogin 白屏链接。")
    _emit(printer, "备选：python spider.py login --cookie")
    from xianyu.qr_browser import login_via_official_page
    from xianyu.mtop import login_snapshot

    try:
        result = await login_via_official_page(timeout=timeout)
    except Exception as exc:
        _emit(printer, f"浏览器扫码失败: {exc}")
        _emit(printer, "改用 Cookie：浏览器登录 www.goofish.com 后，F12 复制 Cookie，再运行 python spider.py login --cookie")
        return 1
    if result.get("logged_in"):
        user = result.get("user") or login_snapshot()
        _emit(printer, f"登录成功 user_id={user.get('user_id') or result.get('user_id') or '-'}")
        return 0
    _emit(printer, result.get("hint") or "未登录")
    return 1


async def _run_cookie_login(*, cookie: str, printer: Printer) -> int:
    from xianyu.mtop import login_snapshot, login_with_cookie

    text = (cookie or "").strip()
    if not text or text == "-":
        if not _stdin_is_interactive():
            _emit(printer, "请提供 Cookie：python spider.py login --cookie 'unb=...; cookie2=...; _m_h5_tk=...'")
            return 1
        _emit(printer, "请粘贴闲鱼网页 Cookie 后回车（需包含 unb，以及 cookie2 或 _m_h5_tk）：")
        text = (await _read_stdin_line()).strip()
    if text.startswith("http"):
        _emit(printer, "这是网页链接，不是 Cookie。请从浏览器 F12 → Application/存储 → Cookie 复制，或改用默认的浏览器扫码登录。")
        return 1
    if "=" not in text:
        _emit(printer, "Cookie 格式不对。")
        return 1
    try:
        await login_with_cookie(text)
    except Exception as exc:
        _emit(printer, f"Cookie 登录失败: {exc}")
        return 1
    user = login_snapshot()
    _emit(printer, f"登录成功 user_id={user.get('user_id') or '-'}")
    return 0


async def run_qr_login(
    *,
    poll_interval: float = 2.0,
    timeout: int = 180,
    printer: Optional[Printer] = None,
) -> int:
    """先画登录码；若官方要拍脸，再弹出 Playwright 完成核身。"""
    print_fn: Printer = printer or print
    from xianyu.mtop import init, login_snapshot, poll_qr_login, start_qr_login, submit_qr_callback

    await init()
    snapshot = login_snapshot()
    if snapshot.get("logged_in"):
        _emit(print_fn, f"已经登录，user_id={snapshot.get('user_id') or '-'}")
        return 0

    result = await start_qr_login()
    ascii_qr = str(result.get("qr_ascii") or "") or qr_ascii(str(result.get("qr_content") or ""))
    _emit(print_fn, "请用闲鱼 App 扫下面的登录二维码，并在手机上点「确认登录」。")
    _emit(print_fn, "若之后要拍脸/身份验证，会自动打开 Playwright 窗口，在那个窗口里完成即可。")
    _emit(print_fn, ascii_qr, end="" if ascii_qr.endswith("\n") else "\n")
    _emit(print_fn, f"session_id={result.get('session_id')}")
    session_id = str(result.get("session_id") or "")
    printed_verify = ""
    printed_trace = ""
    last_progress = ""
    stdin_task: Optional[asyncio.Task] = None
    playwright_tried = False
    try:
        while True:
            status = await poll_qr_login(session_id)
            line = str((status.get("debug") or {}).get("last_trace_line") or "")
            if line and line != printed_trace:
                _emit(print_fn, "追踪: " + line)
                printed_trace = line
            if status.get("logged_in"):
                user = status.get("user") or login_snapshot()
                _emit(print_fn, "")
                _emit(print_fn, f"登录成功 user_id={user.get('user_id') or '-'}")
                return 0
            kind = str(status.get("status") or "").lower()
            if _still_verifying(status, kind):
                kind = "verification_required"
            if kind == "verification_required":
                verify_url = str(status.get("verification_url") or "")
                face_verify = bool(status.get("face_verify"))
                if not face_verify:
                    from xianyu.protocol import is_identity_qr_page

                    face_verify = is_identity_qr_page(verify_url)
                if face_verify:
                    if not playwright_tried:
                        _emit(print_fn, "")
                        _emit(print_fn, "官方要「拍摄脸部」。正在用 Playwright 打开核身页，请在弹出窗口里扫码并拍脸。")
                        if verify_url:
                            _emit(print_fn, verify_url)
                        from xianyu.qr_browser import complete_browser_verify

                        playwright_tried = True
                        printed_verify = verify_url or "face"
                        try:
                            verified = await complete_browser_verify(session_id, timeout=timeout)
                        except Exception as exc:
                            _emit(print_fn, f"Playwright 核身失败: {exc}")
                            if verify_url:
                                opened = _open_default_browser(verify_url)
                                if opened:
                                    _emit(print_fn, "已改为打开系统默认浏览器。拍完不要关页面。")
                            _emit(print_fn, "备选：python spider.py login --browser 或 --cookie")
                            if stdin_task is None and _stdin_is_interactive():
                                stdin_task = asyncio.create_task(_read_stdin_line())
                        else:
                            if verified.get("logged_in"):
                                user = verified.get("user") or login_snapshot()
                                _emit(print_fn, f"登录成功 user_id={user.get('user_id') or verified.get('user_id') or '-'}")
                                return 0
                            _emit(print_fn, verified.get("hint") or "核身窗口已关闭，仍未登录，继续等待。")
                            _emit(print_fn, "备选：python spider.py login --browser 或 --cookie")
                            if stdin_task is None and _stdin_is_interactive():
                                stdin_task = asyncio.create_task(_read_stdin_line())
                    else:
                        _emit(
                            print_fn,
                            "仍在等待核身完成。",
                            end="\r",
                            flush=True,
                        )
                else:
                    verify_ascii = str(status.get("verification_qr_ascii") or "") or qr_ascii(
                        verify_url
                    )
                    if verify_ascii and verify_ascii != printed_verify:
                        _emit(print_fn, "")
                        _emit(
                            print_fn,
                            "需要手机验证。请用闲鱼 App 内的「扫一扫」扫下面这个验证码（不要用系统相机）。",
                        )
                        _emit(print_fn, verify_ascii, end="" if verify_ascii.endswith("\n") else "\n")
                        printed_verify = verify_ascii
                    else:
                        _emit(
                            print_fn,
                            status.get("hint") or "等待手机验证...",
                            end="\r",
                            flush=True,
                        )
            elif kind in {"scanned", "confirmed"}:
                if kind != last_progress:
                    _emit(print_fn, "")
                    _emit(print_fn, status.get("hint") or kind)
                    last_progress = kind
            elif kind in {"expired", "canceled"}:
                _emit(print_fn, "")
                _emit(
                    print_fn,
                    status.get("hint") or "二维码已失效，请重新运行 python spider.py login",
                )
                return 1
            else:
                _emit(print_fn, status.get("hint") or kind, end="\r", flush=True)

            if stdin_task is not None:
                done, _ = await asyncio.wait({stdin_task}, timeout=poll_interval)
                if stdin_task in done:
                    raw = stdin_task.result() or ""
                    pasted = raw.strip()
                    if pasted.startswith("http"):
                        _emit(print_fn, "正在用回调 URL 换登录态...")
                        try:
                            callback = await submit_qr_callback(session_id, pasted)
                        except Exception as exc:
                            _emit(print_fn, f"提交回调失败: {exc}")
                        else:
                            if callback.get("logged_in"):
                                user = callback.get("user") or login_snapshot()
                                _emit(print_fn, f"登录成功 user_id={user.get('user_id') or '-'}")
                                return 0
                            _emit(print_fn, callback.get("hint") or "回调已提交，继续等待")
                            if callback.get("debug", {}).get("last_trace_line"):
                                _emit(print_fn, "追踪: " + callback["debug"]["last_trace_line"])
                    if raw == "" or not _stdin_is_interactive():
                        stdin_task = None
                    else:
                        stdin_task = asyncio.create_task(_read_stdin_line())
            else:
                await asyncio.sleep(poll_interval)
    except KeyboardInterrupt:
        _emit(print_fn, "\n已取消")
        return 130
    finally:
        if stdin_task is not None and not stdin_task.done():
            stdin_task.cancel()
