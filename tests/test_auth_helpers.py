from api import generate_sign, login_snapshot, apply_cookies, current_cookies, logout


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
