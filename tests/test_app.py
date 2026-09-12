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


def test_auth_user_requires_login():
    logout()
    with _client() as client:
        res = client.get("/auth/user")
        assert res.status_code == 401


def test_cookie_login_rejects_empty():
    with _client() as client:
        res = client.post("/auth/cookie", json={"cookie": "not-a-cookie"})
        assert res.status_code == 400


def test_auth_status_probes_goofish(monkeypatch):
    async def fake_user():
        return {"userId": "777"}

    monkeypatch.setattr("xianyu.mtop.fetch_login_user", fake_user)
    logout()
    apply_cookies("unb=777; cookie2=abc")
    with _client() as client:
        res = client.get("/auth/status")
        assert res.status_code == 200
        body = res.json()
        assert body["logged_in"] is True
        assert body["user_id"] == "777"
        assert body["user"]["userId"] == "777"
        user = client.get("/auth/user")
        assert user.status_code == 200
        assert user.json()["logged_in"] is True
    logout()


def test_auth_status_expired_cookies_are_logged_out(monkeypatch):
    async def expired():
        raise RuntimeError("未登录或登录已失效")

    monkeypatch.setattr("xianyu.mtop.fetch_login_user", expired)
    logout()
    apply_cookies("unb=777; cookie2=abc; _m_h5_tk=tok_1; _m_h5_tk_enc=enc")
    with _client() as client:
        res = client.get("/auth/status")
        assert res.status_code == 200
        body = res.json()
        assert body["logged_in"] is False
        assert body["login_expired"] is True
        assert "spider.py login" in body["hint"]
        user = client.get("/auth/user")
        assert user.status_code == 401
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
        assert "verify.htm" in res.text
        assert "拍摄脸部" in res.text
        assert "套娃" in res.text or "不要扫" in res.text
        assert "默认浏览器" in res.text
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


def test_qr_text_endpoint_prints_ascii():
    from xianyu import mtop

    logout()
    mtop._qr_sessions["txt1"] = {
        "t": "1",
        "ck": "2",
        "code_content": "https://qr.goofish.com/s?k=login",
    }
    with _client() as client:
        missing = client.get("/auth/qr/text", params={"session_id": "missing"})
        assert missing.status_code == 404
        res = client.get("/auth/qr/text", params={"session_id": "txt1"})
        assert res.status_code == 200
        assert "text/plain" in res.headers.get("content-type", "")
        assert len(res.text) > 50
    logout()


def test_qr_trace_endpoint_returns_events():
    from xianyu import mtop

    logout()
    missing_client = _client()
    with missing_client as client:
        missing = client.get("/auth/qr/trace", params={"session_id": "missing"})
        assert missing.status_code == 404
    mtop._qr_sessions["tr1"] = {"t": "1", "ck": "2"}
    with _client() as client:
        res = client.get("/auth/qr/trace", params={"session_id": "tr1"})
        assert res.status_code == 200
        body = res.json()
        assert body["session_id"] == "tr1"
        assert "events" in body
        assert "debug" in body
    logout()


def test_qr_callback_rejects_missing_session():
    with _client() as client:
        res = client.post(
            "/auth/qr/callback",
            json={
                "session_id": "missing",
                "url": "https://passport.goofish.com/newlogin/safe/ivCheckLogin.htm?havana_iv_token=x",
            },
        )
        assert res.status_code == 404


def test_search_returns_logged_in_false_without_session(monkeypatch):
    async def fake_scrape(keyword, max_pages=1, filters=None):
        assert keyword == "手机"
        assert max_pages == 1
        assert filters is not None
        assert filters.normalized().sort == "newest"
        return []

    monkeypatch.setattr("xianyu.routers.search.scrape_xianyu_http", fake_scrape)
    logout()
    with _client() as client:
        res = client.post("/search/", json={"keyword": "手机"})
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "success"
        assert body["keyword"] == "手机"
        assert body["logged_in"] is False
        assert body["total_results"] == 0
        assert body["items"] == []
        assert body["filters"]["sort"] == "newest"


def test_search_accepts_filters_and_logged_in_cookie(monkeypatch):
    async def fake_scrape(keyword, max_pages=1, filters=None):
        data = filters.normalized()
        assert keyword == "相机"
        assert max_pages == 2
        assert data.sort == "price_asc"
        assert data.min_price == 100
        assert data.max_price == 800
        assert data.city == "深圳"
        return [{"商品标题": "x", "商品链接": "https://www.goofish.com/item?id=1"}]

    async def fake_save(data_list):
        assert len(data_list) == 1
        return 1, [11]

    monkeypatch.setattr("xianyu.routers.search.scrape_xianyu_http", fake_scrape)
    monkeypatch.setattr("xianyu.routers.search.save_to_db", fake_save)

    async def fake_user():
        return {"userId": "123"}

    monkeypatch.setattr("xianyu.mtop.fetch_login_user", fake_user)
    logout()
    apply_cookies("unb=123; cookie2=abc")
    with _client() as client:
        res = client.post(
            "/search/",
            json={
                "keyword": "相机",
                "max_pages": 2,
                "sort": "price_asc",
                "min_price": 100,
                "max_price": 800,
                "city": "深圳",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["logged_in"] is True
        assert body["user_id"] == "123"
        assert body["new_records"] == 1
        assert body["filters"]["sort"] == "price_asc"
        assert body["filters"]["city"] == "深圳"
        assert body["items"][0]["title"] == "x"
        assert body["items"][0]["item_id"] == "1"
    logout()


def test_search_items_land_on_shelf(monkeypatch):
    async def fake_scrape(keyword, max_pages=1, filters=None):
        return [
            {
                "商品标题": "旧相机",
                "当前售价": "¥800",
                "发货地区": "深圳",
                "卖家昵称": "店主",
                "商品链接": "https://www.goofish.com/item?id=99",
                "商品图片链接": "https://img.example/a.jpg",
                "发布时间": "2026-01-01 12:00",
                "seller_id": "88",
            }
        ]

    monkeypatch.setattr("xianyu.routers.search.scrape_xianyu_http", fake_scrape)
    logout()
    with _client() as client:
        empty = client.get("/products")
        assert empty.status_code == 200
        assert empty.json()["total"] == 0

        res = client.post("/search/", json={"keyword": "相机"})
        assert res.status_code == 200
        item = res.json()["items"][0]
        assert item["title"] == "旧相机"
        assert item["is_new"] is True
        assert item["id"]
        assert item["seller_id"] == "88"

        shelf = client.get("/products", params={"q": "相机"})
        assert shelf.status_code == 200
        assert shelf.json()["total"] == 1
        assert shelf.json()["items"][0]["title"] == "旧相机"

        detail = client.get(f"/products/{item['id']}")
        assert detail.status_code == 200
        assert detail.json()["link"].endswith("id=99")

        missing = client.get("/products/999999")
        assert missing.status_code == 404
    logout()


def test_workbench_is_served():
    with _client() as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "闲鱼工作台" in home.text
        css = client.get("/app.css")
        assert css.status_code == 200
        assert "brand-mark" in css.text
        js = client.get("/app.js")
        assert js.status_code == 200
        assert "闲鱼工作台" in js.text


def test_search_expired_login_continues_anonymously(monkeypatch):
    async def fake_scrape(keyword, max_pages=1, filters=None):
        return []

    async def expired():
        raise RuntimeError("未登录或登录已失效")

    monkeypatch.setattr("xianyu.routers.search.scrape_xianyu_http", fake_scrape)
    monkeypatch.setattr("xianyu.mtop.fetch_login_user", expired)
    logout()
    apply_cookies("unb=123; cookie2=abc; _m_h5_tk=tok_1; _m_h5_tk_enc=enc")
    with _client() as client:
        res = client.post("/search/", json={"keyword": "手机"})
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "success"
        assert body["logged_in"] is False
        assert body["login_expired"] is True
        assert "spider.py login" in body["hint"]
    logout()


def test_search_rejects_unknown_sort():
    with _client() as client:
        res = client.post("/search/", json={"keyword": "手机", "sort": "hot"})
        assert res.status_code == 422

