from fastapi.testclient import TestClient

from xianyu.app import create_app
from xianyu.mtop import apply_cookies, logout


def _client():
    app = create_app(connect_xianyu=False, db_url="sqlite://:memory:")
    return TestClient(app)


def test_auth_status_logged_out():
    logout()
    with _client() as client:
        res = client.get("/auth/status")
        assert res.status_code == 200
        body = res.json()
        assert body["logged_in"] is False


def test_cookie_login_rejects_empty():
    with _client() as client:
        res = client.post("/auth/cookie", json={"cookie": "not-a-cookie"})
        assert res.status_code == 400


def test_im_start_requires_login():
    logout()
    with _client() as client:
        res = client.post("/im/start")
        assert res.status_code == 401


def test_im_config_roundtrip():
    with _client() as client:
        got = client.get("/im/config")
        assert got.status_code == 200
        assert got.json()["enabled"] is False

        updated = client.put(
            "/im/config",
            json={
                "enabled": True,
                "default_reply": "在的",
                "keyword_replies": [{"keyword": "刀", "reply": "可小刀"}],
                "webhook_url": "http://127.0.0.1:9/hook",
            },
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["enabled"] is True
        assert body["default_reply"] == "在的"
        assert body["keyword_replies"][0]["keyword"] == "刀"

        again = client.get("/im/config")
        assert again.json()["default_reply"] == "在的"


def test_im_messages_empty():
    with _client() as client:
        res = client.get("/im/messages")
        assert res.status_code == 200
        assert res.json() == []


def test_login_snapshot_via_cookies_without_goofish():
    logout()
    apply_cookies("unb=777; cookie2=abc")
    with _client() as client:
        res = client.get("/auth/status")
        assert res.status_code == 200
        assert res.json()["logged_in"] is True
        assert res.json()["user_id"] == "777"
    logout()
