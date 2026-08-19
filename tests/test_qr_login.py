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


def test_poll_qr_verification_then_expired_still_exchanges_token():
    mtop.logout()
    mtop._qr_sessions["s3"] = {"t": "1", "ck": "2", "csrf": "", "cookie2": ""}
    confirm_need_verify = _query_response(
        "CONFIRMED",
        extra={
            "iframeRedirect": True,
            "iframeRedirectUrl": "https://passport.goofish.com/iv/verify.htm",
            "token": "login-token-1",
        },
    )
    expired = _query_response("EXPIRED")
    empty = httpx.Response(
        200,
        json={"content": {"success": False}},
        request=httpx.Request("POST", "https://passport.goofish.com/login_token/login.do"),
    )
    logged_in = httpx.Response(
        200,
        headers=[("set-cookie", "unb=888; Path=/"), ("set-cookie", "sgcookie=zz; Path=/")],
        json={"content": {"success": True}},
        request=httpx.Request("POST", "https://passport.goofish.com/login_token/login.do"),
    )
    phase = {"name": "verify"}

    async def fake_post(url, **kwargs):
        text = str(url)
        if "query.do" in text:
            return confirm_need_verify if phase["name"] == "verify" else expired
        if phase["name"] == "done":
            return logged_in
        return empty

    async def run():
        with (
            patch.object(mtop.client, "post", side_effect=fake_post),
            patch.object(mtop.client, "get", AsyncMock(return_value=empty)),
            patch.object(mtop, "init_h5tk", AsyncMock()),
            patch.object(mtop, "fetch_login_user", AsyncMock(side_effect=RuntimeError("mtop 未登录"))),
        ):
            first = await mtop.poll_qr_login("s3")
            phase["name"] = "done"
            second = await mtop.poll_qr_login("s3")
            return first, second

    first, second = asyncio.run(run())
    assert first["logged_in"] is False
    assert first["status"] == "verification_required"
    assert first["verification_url"].endswith("verify.htm")
    assert second["logged_in"] is True
    assert mtop.login_snapshot()["user_id"] == "888"
    mtop.logout()


def test_poll_qr_expired_during_verification_is_not_treated_as_failure():
    mtop.logout()
    mtop._qr_sessions["s4"] = {
        "t": "1",
        "ck": "2",
        "csrf": "",
        "cookie2": "",
        "login_token": "keep-me",
        "verification_pending": True,
        "verification_url": "https://passport.goofish.com/iv/verify.htm",
    }
    expired = _query_response("EXPIRED")
    empty = httpx.Response(
        200,
        json={},
        request=httpx.Request("POST", "https://passport.goofish.com/login_token/login.do"),
    )

    async def fake_post(url, **kwargs):
        text = str(url)
        if "query.do" in text:
            return expired
        return empty

    async def run():
        with (
            patch.object(mtop.client, "post", side_effect=fake_post),
            patch.object(mtop.client, "get", AsyncMock(return_value=empty)),
            patch.object(mtop, "init_h5tk", AsyncMock()),
            patch.object(mtop, "fetch_login_user", AsyncMock(side_effect=RuntimeError("mtop 未登录"))),
        ):
            return await mtop.poll_qr_login("s4")

    result = asyncio.run(run())
    assert result["logged_in"] is False
    assert result["status"] == "verification_required"
    assert "不要重新生成" in result["hint"]
    mtop.logout()
