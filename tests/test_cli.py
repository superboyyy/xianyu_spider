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


def test_cli_face_verify_does_not_print_link_qr():
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
            patch("xianyu.cli._open_default_browser", return_value=True) as open_browser,
        ):
            code = await run_qr_login(poll_interval=0, printer=printed)
            open_browser.assert_called_with("https://passport.goofish.com/iv/verify.htm")
            return code

    code = asyncio.run(run())
    assert code == 0
    blob = "\n".join(printed.chunks)
    assert "QRLOGIN" in blob
    assert "拍摄脸部" in blob or "拍脸" in blob
    assert "https://passport.goofish.com/iv/verify.htm" in blob
    assert "默认浏览器" in blob


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

    async def run():
        with (
            patch("xianyu.mtop.init", AsyncMock()),
            patch("xianyu.mtop.login_snapshot", return_value={"logged_in": False}),
            patch("xianyu.mtop.start_qr_login", side_effect=fake_start),
            patch("xianyu.mtop.poll_qr_login", side_effect=fake_poll),
            patch("xianyu.cli._open_default_browser", return_value=True),
        ):
            return await run_qr_login(poll_interval=0, printer=printed)

    code = asyncio.run(run())
    assert code == 0
    blob = "\n".join(printed.chunks)
    assert "8" in blob
    assert "请重新运行" not in blob
