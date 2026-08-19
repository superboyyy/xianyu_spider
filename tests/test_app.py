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


def test_qr_continue_page_renders_form():
    from xianyu import mtop

    logout()
    mtop._qr_sessions["cont1"] = {
        "t": "1",
        "ck": "2",
        "verification_url": "https://passport.goofish.com/iv/verify.htm",
        "verification_pending": True,
    }
    with _client() as client:
        missing = client.get("/auth/qr/continue", params={"session_id": "missing"})
        assert missing.status_code == 404
        res = client.get("/auth/qr/continue", params={"session_id": "cont1"})
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "粘贴" in res.text
        assert "打开本机浏览器" in res.text
        assert "verify.htm" in res.text
        assert "data:image/png;base64," in res.text
        assert "用闲鱼 App 扫" in res.text
    logout()


def test_qr_browser_starts_without_launching_chrome(monkeypatch):
    from xianyu import mtop, qr_browser

    async def fake_run(session_id: str):
        return None

    monkeypatch.setattr(qr_browser, "_run_browser_verify", fake_run)
    qr_browser._jobs.clear()
    logout()
    mtop._qr_sessions["b1"] = {
        "t": "1",
        "ck": "2",
        "verification_url": "https://passport.goofish.com/iv/verify.htm",
    }
    with _client() as client:
        missing = client.post("/auth/qr/browser", params={"session_id": "missing"})
        assert missing.status_code == 404
        res = client.post("/auth/qr/browser", params={"session_id": "b1"})
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["status"] == "running"
        status = client.get("/auth/qr/browser", params={"session_id": "b1"})
        assert status.status_code == 200
        assert status.json()["status"] in {"running", "done", "error"}
    logout()
