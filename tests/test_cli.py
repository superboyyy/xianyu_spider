import asyncio
from unittest.mock import AsyncMock, patch

from xianyu.cli import run_qr_login


class _Capture:
    def __init__(self):
        self.chunks = []

    def __call__(self, *args, **kwargs):
        self.chunks.append(" ".join(str(a) for a in args))


def test_cli_prints_login_qr_then_success():
    printed = _Capture()

    async def fake_start():
        return {"session_id": "s-cli", "qr_ascii": "QRLOGIN\n", "qr_content": "x"}

    async def fake_poll(session_id):
        assert session_id == "s-cli"
        return {"logged_in": True, "user": {"user_id": "99"}}

    async def run():
        with (
            patch("xianyu.mtop.init", AsyncMock()),
            patch("xianyu.mtop.login_snapshot", return_value={"logged_in": False}),
            patch("xianyu.mtop.start_qr_login", side_effect=fake_start),
            patch("xianyu.mtop.poll_qr_login", side_effect=fake_poll),
        ):
            return await run_qr_login(poll_interval=0, printer=printed)

    code = asyncio.run(run())
    assert code == 0
    blob = "\n".join(printed.chunks)
    assert "QRLOGIN" in blob
    assert "99" in blob


def test_cli_prints_verification_qr():
    printed = _Capture()
    polls = iter(
        [
            {
                "logged_in": False,
                "status": "verification_required",
                "verification_qr_ascii": "QRVERIFY\n",
                "hint": "wait",
            },
            {"logged_in": True, "user": {"user_id": "7"}},
        ]
    )

    async def fake_start():
        return {"session_id": "s-v", "qr_ascii": "QRLOGIN\n"}

    async def fake_poll(session_id):
        return next(polls)

    async def run():
        with (
            patch("xianyu.mtop.init", AsyncMock()),
            patch("xianyu.mtop.login_snapshot", return_value={"logged_in": False}),
            patch("xianyu.mtop.start_qr_login", side_effect=fake_start),
            patch("xianyu.mtop.poll_qr_login", side_effect=fake_poll),
        ):
            return await run_qr_login(poll_interval=0, printer=printed)

    code = asyncio.run(run())
    assert code == 0
    blob = "\n".join(printed.chunks)
    assert "QRLOGIN" in blob
    assert "QRVERIFY" in blob


def test_cli_face_verify_opens_playwright():
    printed = _Capture()
    polls = iter(
        [
            {
                "logged_in": False,
                "status": "verification_required",
                "face_verify": True,
                "verification_url": "https://passport.goofish.com/iv/verify.htm",
                "verification_qr_ascii": "",
                "continue_url": "/auth/qr/continue?session_id=s-v",
                "hint": "拍摄脸部",
            },
        ]
    )

    async def fake_start():
        return {"session_id": "s-v", "qr_ascii": "QRLOGIN\n"}

    async def fake_poll(session_id):
        return next(polls)

    async def fake_verify(session_id, *, timeout=180):
        assert session_id == "s-v"
        return {"ok": True, "logged_in": True, "user_id": "7", "user": {"user_id": "7"}}

    async def run():
        with (
            patch("xianyu.mtop.init", AsyncMock()),
            patch("xianyu.mtop.login_snapshot", return_value={"logged_in": False}),
            patch("xianyu.mtop.start_qr_login", side_effect=fake_start),
            patch("xianyu.mtop.poll_qr_login", side_effect=fake_poll),
            patch("xianyu.qr_browser.complete_browser_verify", side_effect=fake_verify) as verify,
        ):
            code = await run_qr_login(poll_interval=0, printer=printed)
            verify.assert_awaited()
            return code

    code = asyncio.run(run())
    assert code == 0
    blob = "\n".join(printed.chunks)
    assert "QRLOGIN" in blob
    assert "拍摄脸部" in blob or "拍脸" in blob
    assert "https://passport.goofish.com/iv/verify.htm" in blob
    assert "Playwright" in blob
    assert "QRVERIFY" not in blob


def test_cli_prints_scanned_hint():
    printed = _Capture()
    polls = iter(
        [
            {
                "logged_in": False,
                "status": "scanned",
                "hint": "已扫码，请在闲鱼 App 里点「确认登录」。只扫码不会登录。",
            },
            {"logged_in": True, "user": {"user_id": "3"}},
        ]
    )

    async def fake_start():
        return {"session_id": "s-scan", "qr_ascii": "QRLOGIN\n"}

    async def fake_poll(session_id):
        return next(polls)

    async def run():
        with (
            patch("xianyu.mtop.init", AsyncMock()),
            patch("xianyu.mtop.login_snapshot", return_value={"logged_in": False}),
            patch("xianyu.mtop.start_qr_login", side_effect=fake_start),
            patch("xianyu.mtop.poll_qr_login", side_effect=fake_poll),
        ):
            return await run_qr_login(poll_interval=0, printer=printed)

    code = asyncio.run(run())
    assert code == 0
    blob = "\n".join(printed.chunks)
    assert "已扫码" in blob
    assert "确认登录" in blob


def test_cli_ignores_expired_while_face_verify_pending():
    printed = _Capture()
    polls = iter(
        [
            {
                "logged_in": False,
                "status": "expired",
                "face_verify": True,
                "verification_pending": True,
                "verification_url": "https://passport.goofish.com/iv/verify.htm",
                "hint": "等待拍脸",
            },
            {"logged_in": True, "user": {"user_id": "8"}},
        ]
    )

    async def fake_start():
        return {"session_id": "s-exp", "qr_ascii": "QRLOGIN\n"}

    async def fake_poll(session_id):
        return next(polls)

    async def fake_verify(session_id, *, timeout=180):
        return {"ok": True, "logged_in": True, "user_id": "8", "user": {"user_id": "8"}}

    async def run():
        with (
            patch("xianyu.mtop.init", AsyncMock()),
            patch("xianyu.mtop.login_snapshot", return_value={"logged_in": False}),
            patch("xianyu.mtop.start_qr_login", side_effect=fake_start),
            patch("xianyu.mtop.poll_qr_login", side_effect=fake_poll),
            patch("xianyu.qr_browser.complete_browser_verify", side_effect=fake_verify),
        ):
            return await run_qr_login(poll_interval=0, printer=printed)

    code = asyncio.run(run())
    assert code == 0
    blob = "\n".join(printed.chunks)
    assert "8" in blob
    assert "请重新运行" not in blob


def test_cli_browser_login_imports_official_page_cookies():
    printed = _Capture()

    async def fake_browser(**kwargs):
        return {"ok": True, "logged_in": True, "user_id": "2048", "user": {"user_id": "2048"}}

    async def run():
        with (
            patch("xianyu.mtop.init", AsyncMock()),
            patch("xianyu.mtop.login_snapshot", return_value={"logged_in": False}),
            patch("xianyu.qr_browser.login_via_official_page", side_effect=fake_browser),
        ):
            from xianyu.cli import run_login

            return await run_login(mode="browser", printer=printed)

    code = asyncio.run(run())
    assert code == 0
    blob = "\n".join(printed.chunks)
    assert "官方登录页" in blob
    assert "2048" in blob


def test_cli_cookie_login_rejects_ivcheck_url():
    printed = _Capture()

    async def run():
        with (
            patch("xianyu.mtop.init", AsyncMock()),
            patch("xianyu.mtop.login_snapshot", return_value={"logged_in": False}),
        ):
            from xianyu.cli import run_login

            return await run_login(
                mode="cookie",
                cookie="https://passport.goofish.com/newlogin/safe/ivCheckLogin.htm?havana_iv_token=x",
                printer=printed,
            )

    code = asyncio.run(run())
    assert code == 1
    blob = "\n".join(printed.chunks)
    assert "不是 Cookie" in blob


def test_cli_cookie_login_success():
    printed = _Capture()

    async def fake_cookie(text):
        assert "unb=9" in text
        return {"logged_in": True, "user_id": "9"}

    async def run():
        with (
            patch("xianyu.mtop.init", AsyncMock()),
            patch("xianyu.mtop.login_snapshot", side_effect=[{"logged_in": False}, {"logged_in": True, "user_id": "9"}]),
            patch("xianyu.mtop.login_with_cookie", side_effect=fake_cookie),
        ):
            from xianyu.cli import run_login

            return await run_login(mode="cookie", cookie="unb=9; cookie2=abc; _m_h5_tk=tok", printer=printed)

    code = asyncio.run(run())
    assert code == 0
    blob = "\n".join(printed.chunks)
    assert "9" in blob


def test_cli_default_login_uses_terminal_qr():
    printed = _Capture()

    async def fake_start():
        return {"session_id": "s-default", "qr_ascii": "QRLOGIN\n", "qr_content": "x"}

    async def fake_poll(session_id):
        return {"logged_in": True, "user": {"user_id": "11"}}

    async def run():
        with (
            patch("xianyu.mtop.init", AsyncMock()),
            patch("xianyu.mtop.login_snapshot", return_value={"logged_in": False}),
            patch("xianyu.mtop.start_qr_login", side_effect=fake_start),
            patch("xianyu.mtop.poll_qr_login", side_effect=fake_poll),
        ):
            from xianyu.cli import run_login

            return await run_login(printer=printed)

    code = asyncio.run(run())
    assert code == 0
    blob = "\n".join(printed.chunks)
    assert "QRLOGIN" in blob
    assert "11" in blob
    assert "官方登录页" not in blob
