"""命令行扫码登录：在终端打印二维码并轮询直到登录成功。"""

from __future__ import annotations

import asyncio
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


async def run_qr_login(
    *,
    poll_interval: float = 2.0,
    printer: Optional[Printer] = None,
) -> int:
    """在终端画出登录/验证二维码，直到登录成功。返回进程退出码。"""
    print_fn: Printer = printer or print
    from xianyu.mtop import init, login_snapshot, poll_qr_login, start_qr_login

    await init()
    snapshot = login_snapshot()
    if snapshot.get("logged_in"):
        _emit(print_fn, f"已经登录，user_id={snapshot.get('user_id') or '-'}")
        return 0

    result = await start_qr_login()
    ascii_qr = str(result.get("qr_ascii") or "") or qr_ascii(str(result.get("qr_content") or ""))
    _emit(print_fn, "请用闲鱼 App 扫下面的登录二维码，并在手机上点「确认登录」。")
    _emit(print_fn, ascii_qr, end="" if ascii_qr.endswith("\n") else "\n")
    _emit(print_fn, f"session_id={result.get('session_id')}")
    session_id = str(result.get("session_id") or "")
    printed_verify = ""
    printed_trace = ""
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
            kind = str(status.get("status") or "")
            if kind == "verification_required":
                verify_url = str(status.get("verification_url") or "")
                face_verify = bool(status.get("face_verify"))
                if not face_verify:
                    from xianyu.protocol import is_identity_qr_page

                    face_verify = is_identity_qr_page(verify_url)
                if face_verify:
                    if verify_url != printed_verify:
                        _emit(print_fn, "")
                        _emit(
                            print_fn,
                            "官方要「拍摄脸部」。不要扫下面这个链接生成的码，请直接在电脑打开它。",
                        )
                        if verify_url:
                            _emit(print_fn, verify_url)
                            opened = _open_default_browser(verify_url)
                            if opened:
                                _emit(print_fn, "已用系统默认浏览器打开。用闲鱼 App 扫浏览器里的码并拍脸，拍完不要关页面，在此等待登录成功。")
                            else:
                                _emit(print_fn, "请 Ctrl+单击上面的链接，用默认浏览器打开后拍脸。")
                        printed_verify = verify_url or "face"
                    else:
                        _emit(
                            print_fn,
                            status.get("hint") or "等待拍脸验证...",
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
            elif kind in {"expired", "canceled"}:
                _emit(print_fn, "")
                _emit(
                    print_fn,
                    status.get("hint") or "二维码已失效，请重新运行 python spider.py login",
                )
                return 1
            else:
                _emit(print_fn, status.get("hint") or kind, end="\r", flush=True)
            await asyncio.sleep(poll_interval)
    except KeyboardInterrupt:
        _emit(print_fn, "\n已取消")
        return 130
