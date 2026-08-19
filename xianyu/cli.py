"""命令行扫码登录：在终端打印二维码并轮询直到登录成功。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Optional

from xianyu.protocol import qr_ascii

Printer = Callable[..., None]


def _emit(printer: Printer, *args: Any, **kwargs: Any) -> None:
    printer(*args, **kwargs)


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
    try:
        while True:
            status = await poll_qr_login(session_id)
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
                            "官方要「拍摄脸部」。不要扫验证页链接生成的码，那会在手机上套娃。",
                        )
                        _emit(print_fn, "请用闲鱼 App 扫【电脑浏览器窗口里】的二维码，按提示拍脸，拍完不要关窗口。")
                        if verify_url:
                            _emit(print_fn, verify_url)
                        try:
                            from xianyu.qr_browser import start_browser_verify

                            opened = await start_browser_verify(session_id)
                            _emit(print_fn, opened.get("hint") or "已尝试打开本机浏览器。")
                        except Exception as exc:
                            continue_url = status.get("continue_url") or ""
                            _emit(
                                print_fn,
                                f"无法自动打开浏览器：{exc}。请在电脑打开 {continue_url or 'continue_url'} 后点「打开本机浏览器」。",
                            )
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
