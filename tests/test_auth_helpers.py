from api import generate_sign, login_snapshot, apply_cookies, current_cookies, logout
from xianyu.protocol import (
    cookie_user_id,
    cookies_from_query_url,
    has_login_cookies,
    has_official_session_cookies,
    is_qr_confirmed,
    is_identity_qr_page,
    is_risk_verify_url,
    normalize_qr_status,
    qr_ascii,
    qr_png_base64,
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
    assert is_identity_qr_page("https://passport.goofish.com/iv/verify.htm") is True


def test_iv_check_login_url_is_callback_not_risk():
    from xianyu.protocol import is_iv_check_login_url, is_login_success_url

    url = (
        "https://passport.goofish.com/newlogin/safe/ivCheckLogin.htm"
        "?havana_iv_token=CN-SPLIT-xxx&appName=xianyu&ck=abc&sg=def"
    )
    assert is_iv_check_login_url(url) is True
    assert is_risk_verify_url(url) is False
    assert is_login_success_url(url) is True
    assert is_identity_qr_page(url) is False


def test_havana_verify_page_with_token_is_not_callback():
    from xianyu.protocol import is_iv_check_login_url, is_login_success_url

    verify = (
        "https://passport.goofish.com/iv/verify.htm"
        "?havana_iv_token=AAA&from=qr&appName=xianyu"
    )
    assert is_iv_check_login_url(verify) is False
    assert is_risk_verify_url(verify) is True
    assert is_identity_qr_page(verify) is True
    assert is_login_success_url(verify) is False


def test_qr_png_base64_from_verify_url():
    raw = qr_png_base64("https://passport.goofish.com/iv/verify.htm")
    assert len(raw) > 100
    import base64

    assert base64.b64decode(raw)[:8] == b"\x89PNG\r\n\x1a\n"



def test_qr_ascii_from_verify_url():
    text = qr_ascii("https://passport.goofish.com/iv/verify.htm")
    assert "\n" in text
    assert len(text) > 50


def test_import_playwright_cookies_sets_unb():
    from xianyu.qr_browser import import_playwright_cookies
    from xianyu.mtop import login_snapshot, logout

    logout()
    import_playwright_cookies([{"name": "unb", "value": "42"}])
    assert login_snapshot()["user_id"] == "42"
    logout()


def test_official_session_cookies_need_all_three():
    assert has_official_session_cookies({}) is False
    assert has_official_session_cookies({"unb": "1"}) is False
    assert has_official_session_cookies({"unb": "1", "cookie2": "c"}) is False
    assert has_official_session_cookies({"unb": "1", "cookie2": "c", "_m_h5_tk": "t"}) is True
