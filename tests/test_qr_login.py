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


def test_poll_qr_success_iframe_async_urls_are_not_phone_verify():
    mtop.logout()
    mtop._qr_sessions["s5"] = {"t": "1", "ck": "2", "csrf": "", "cookie2": ""}
    confirmed = _query_response(
        "CONFIRMED",
        extra={
            "iframeRedirect": True,
            "iframeRedirectUrl": "https://www.goofish.com/",
            "processFinished": True,
            "asyncUrls": [
                "https://passport.goofish.com/newlogin/asynchtml.do?unb=321&sgcookie=tok123&cookie2=c2"
            ],
        },
    )
    empty = httpx.Response(
        200,
        json={},
        request=httpx.Request("GET", "https://passport.goofish.com/newlogin/asynchtml.do"),
    )
    gets: list[str] = []

    async def fake_get(url, **kwargs):
        gets.append(str(url))
        return empty

    async def run():
        with (
            patch.object(mtop.client, "post", AsyncMock(return_value=confirmed)),
            patch.object(mtop.client, "get", side_effect=fake_get),
            patch.object(mtop, "init_h5tk", AsyncMock()),
            patch.object(mtop, "fetch_login_user", AsyncMock(side_effect=RuntimeError("mtop 未登录"))),
        ):
            return await mtop.poll_qr_login("s5")

    result = asyncio.run(run())
    assert result["logged_in"] is True
    assert result["status"] != "verification_required"
    assert mtop.login_snapshot()["user_id"] == "321"
    assert any("asynchtml.do" in item for item in gets)
    mtop.logout()


def test_poll_qr_does_not_fetch_verification_page():
    mtop.logout()
    mtop._qr_sessions["s6"] = {"t": "1", "ck": "2", "csrf": "", "cookie2": ""}
    confirmed = _query_response(
        "CONFIRMED",
        extra={
            "iframeRedirect": True,
            "iframeRedirectUrl": "https://passport.goofish.com/iv/verify.htm",
            "token": "login-token-2",
        },
    )
    empty = httpx.Response(
        200,
        json={},
        request=httpx.Request("POST", "https://passport.goofish.com/login_token/login.do"),
    )
    gets: list[str] = []

    async def fake_post(url, **kwargs):
        text = str(url)
        if "query.do" in text:
            return confirmed
        return empty

    async def fake_get(url, **kwargs):
        gets.append(str(url))
        return empty

    async def run():
        with (
            patch.object(mtop.client, "post", side_effect=fake_post),
            patch.object(mtop.client, "get", side_effect=fake_get),
            patch.object(mtop, "init_h5tk", AsyncMock()),
            patch.object(mtop, "fetch_login_user", AsyncMock(side_effect=RuntimeError("mtop 未登录"))),
        ):
            return await mtop.poll_qr_login("s6")

    result = asyncio.run(run())
    assert result["status"] == "verification_required"
    assert result["continue_url"].endswith("session_id=s6")
    assert result["verification_url"].endswith("verify.htm")
    assert result["face_verify"] is True
    assert "拍摄脸部" in result["hint"] or "套娃" in result["hint"]
    assert not result["verification_qr_ascii"]
    assert not any("verify.htm" in item for item in gets)
    mtop.logout()


def test_poll_qr_does_not_fetch_havana_verify_page_with_token():
    mtop.logout()
    mtop._qr_sessions["s7"] = {"t": "1", "ck": "2", "csrf": "", "cookie2": ""}
    verify_url = (
        "https://passport.goofish.com/iv/verify.htm"
        "?havana_iv_token=AAA&from=qr"
    )
    confirmed = _query_response(
        "CONFIRMED",
        extra={
            "iframeRedirect": True,
            "iframeRedirectUrl": verify_url,
            "token": "login-token-3",
        },
    )
    empty = httpx.Response(
        200,
        json={},
        request=httpx.Request("POST", "https://passport.goofish.com/login_token/login.do"),
    )
    gets: list[str] = []

    async def fake_post(url, **kwargs):
        text = str(url)
        if "query.do" in text:
            return confirmed
        return empty

    async def fake_get(url, **kwargs):
        gets.append(str(url))
        return empty

    async def run():
        with (
            patch.object(mtop.client, "post", side_effect=fake_post),
            patch.object(mtop.client, "get", side_effect=fake_get),
            patch.object(mtop, "init_h5tk", AsyncMock()),
            patch.object(mtop, "fetch_login_user", AsyncMock(side_effect=RuntimeError("mtop 未登录"))),
        ):
            return await mtop.poll_qr_login("s7")

    result = asyncio.run(run())
    assert result["status"] == "verification_required"
    assert result["face_verify"] is True
    assert result["verification_pending"] is True
    assert "havana_iv_token=AAA" in result["verification_url"]
    assert not mtop._qr_sessions["s7"].get("callback_url")
    assert not mtop._qr_sessions["s7"].get("havana_iv_token")
    assert not any("verify.htm" in item for item in gets)
    assert not any("havana_iv_token=AAA" in item for item in gets)
    mtop.logout()


def test_submit_qr_callback_stores_havana_token():
    mtop.logout()
    mtop._qr_sessions["cb1"] = {
        "t": "1",
        "ck": "2",
        "login_token": "tok",
        "verification_pending": True,
    }
    url = (
        "https://passport.goofish.com/newlogin/safe/ivCheckLogin.htm"
        "?havana_iv_token=CN-SPLIT-abc&appName=xianyu"
    )
    empty = httpx.Response(
        200,
        json={},
        request=httpx.Request("GET", url),
    )

    async def run():
        with (
            patch.object(mtop.client, "get", AsyncMock(return_value=empty)),
            patch.object(mtop.client, "post", AsyncMock(return_value=empty)),
            patch.object(mtop, "init_h5tk", AsyncMock()),
            patch.object(mtop, "fetch_login_user", AsyncMock(side_effect=RuntimeError("mtop 未登录"))),
        ):
            return await mtop.submit_qr_callback("cb1", url)

    result = asyncio.run(run())
    assert mtop._qr_sessions["cb1"]["havana_iv_token"] == "CN-SPLIT-abc"
    assert result["logged_in"] is False
    mtop.logout()
