import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from xianyu import mtop


def _query_response(status: str, extra: dict | None = None, cookies: list[str] | None = None) -> httpx.Response:
    data = {"qrCodeStatus": status}
    if extra:
        data.update(extra)
    headers = [(("set-cookie", item)) for item in cookies or []]
    return httpx.Response(
        200,
        headers=headers,
        json={"content": {"data": data}},
        request=httpx.Request("POST", "https://passport.goofish.com/newlogin/qrcode/query.do"),
    )


def test_poll_qr_scaned_is_not_logged_in():
    mtop.logout()
    mtop._qr_sessions["s1"] = {"t": "1", "ck": "2", "csrf": "", "cookie2": ""}

    async def run():
        with patch.object(mtop.client, "post", AsyncMock(return_value=_query_response("SCANED"))):
            return await mtop.poll_qr_login("s1")

    result = asyncio.run(run())
    assert result["logged_in"] is False
    assert result["status"] == "scanned"
    assert "确认" in result["hint"]
    mtop.logout()


def test_poll_qr_confirmed_keeps_login_after_cookie_ingest():
    mtop.logout()
    mtop._qr_sessions["s2"] = {"t": "1", "ck": "2", "csrf": "", "cookie2": ""}
    confirmed = _query_response(
        "CONFIRMED",
        cookies=["unb=555; Path=/", "sgcookie=abc; Path=/"],
    )

    async def run():
        with (
            patch.object(mtop.client, "post", AsyncMock(return_value=confirmed)),
            patch.object(mtop, "init_h5tk", AsyncMock()),
            patch.object(mtop, "fetch_login_user", AsyncMock(side_effect=RuntimeError("mtop 未登录"))),
        ):
            first = await mtop.poll_qr_login("s2")
            second = await mtop.poll_qr_login("s2")
            return first, second

    first, second = asyncio.run(run())
    assert first["logged_in"] is True
    assert first["user"]["user_id"] == "555"
    assert second["logged_in"] is True
    assert mtop.login_snapshot()["logged_in"] is True
    mtop.logout()
