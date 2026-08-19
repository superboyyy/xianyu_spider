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
