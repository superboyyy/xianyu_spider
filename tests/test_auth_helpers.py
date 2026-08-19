from api import generate_sign, login_snapshot, apply_cookies, current_cookies, logout
from xianyu.protocol import (
    cookie_user_id,
    cookies_from_query_url,
    has_login_cookies,
    is_qr_confirmed,
    is_risk_verify_url,
    normalize_qr_status,
    qr_status_hint,
)


def test_generate_sign_stable():
    sign = generate_sign("token", "34839810", {"foo": "bar"}, 1700000000000)
    assert sign == generate_sign("token", "34839810", {"foo": "bar"}, 1700000000000)
    assert len(sign) == 32


def test_cookie_login_snapshot_without_network():
    logout()
    apply_cookies("unb=2048; cookie2=xyz")
    cookies = current_cookies()
    assert cookies["unb"] == "2048"
    snap = login_snapshot()
    assert snap["logged_in"] is True
    assert snap["user_id"] == "2048"
    logout()
    assert login_snapshot()["logged_in"] is False


def test_normalize_qr_status_scaned_is_not_confirmed():
    assert normalize_qr_status("SCANED") == "scanned"
    assert normalize_qr_status("SCANNED") == "scanned"
    assert is_qr_confirmed("SCANED") is False
    assert is_qr_confirmed("CONFIRMED") is True
    assert "确认" in qr_status_hint("SCANED")


def test_cookie_user_id_and_login_cookies():
    assert cookie_user_id({"unb": "9"}) == "9"
    assert cookie_user_id({"sn": "12345"}) == "12345"
    assert cookie_user_id({"sn": "nick"}) == ""
    assert has_login_cookies({"sgcookie": "x"}) is True
    assert has_login_cookies({"cookie2": "x"}) is False


def test_cookies_from_query_url_and_risk_verify():
    url = (
        "https://passport.goofish.com/newlogin/asynchtml.do"
        "?unb=321&sgcookie=tok123&cookie2=c2&target=https://www.goofish.com/"
    )
    cookies = cookies_from_query_url(url)
    assert cookies["unb"] == "321"
    assert cookies["sgcookie"] == "tok123"
    assert cookies["cookie2"] == "c2"
    assert is_risk_verify_url("https://passport.goofish.com/iv/verify.htm") is True
    assert is_risk_verify_url("https://www.goofish.com/") is False
