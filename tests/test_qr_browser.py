from xianyu.qr_browser import OFFICIAL_LOGIN_URL, _cookie_list_logged_in


def test_official_login_url_matches_goofish_cli():
    assert OFFICIAL_LOGIN_URL == "https://www.goofish.com/login"


def test_cookie_list_logged_in_requires_unb_cookie2_and_h5tk():
    assert _cookie_list_logged_in([]) is False
    assert _cookie_list_logged_in([{"name": "unb", "value": "1"}]) is False
    assert _cookie_list_logged_in(
        [
            {"name": "unb", "value": "1"},
            {"name": "cookie2", "value": "c"},
        ]
    ) is False
    assert _cookie_list_logged_in(
        [
            {"name": "unb", "value": "1"},
            {"name": "cookie2", "value": "c"},
            {"name": "_m_h5_tk", "value": "t"},
        ]
    ) is True
