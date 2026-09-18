from fastapi.testclient import TestClient

from xianyu.app import create_app
from xianyu.mtop import logout


def _client():
    app = create_app(connect_xianyu=False, db_url="sqlite://:memory:")
    return TestClient(app)


def test_pricing_helpers():
    from xianyu.pricing import parse_price, summarize_prices

    assert parse_price("¥1,200") == 1200
    assert parse_price("1.5万") == 15000
    stats = summarize_prices([100, 200, 300, 400])
    assert stats["sample_n"] == 4
    assert stats["median"] == 250
    assert stats["mean"] == 250


def test_watch_crud_and_manual_run(monkeypatch):
    async def fake_scrape(keyword, max_pages=1, filters=None):
        return [
            {
                "商品标题": f"{keyword} 测试机",
                "当前售价": "¥900",
                "发货地区": "深圳",
                "卖家昵称": "店主",
                "商品链接": "https://www.goofish.com/item?id=501",
                "商品图片链接": "https://img.example/a.jpg",
                "发布时间": "2026-01-01 12:00",
            }
        ]

    monkeypatch.setattr("xianyu.watch.runner.scrape_xianyu_http", fake_scrape)
    logout()
    with _client() as client:
        created = client.post(
            "/watches",
            json={
                "name": "测试",
                "keyword": "相机",
                "target_price": 1000,
                "interval_minutes": 15,
                "notify_new": True,
                "notify_below_target": True,
            },
        )
        assert created.status_code == 200
        watch_id = created.json()["id"]

        listed = client.get("/watches")
        assert listed.status_code == 200
        assert any(item["id"] == watch_id for item in listed.json()["items"])

        ran = client.post(f"/watches/{watch_id}/run")
        assert ran.status_code == 200
        body = ran.json()
        assert body["total_results"] == 1
        assert body["new_records"] == 1

        stats = client.get("/products/stats", params={"q": "相机"})
        assert stats.status_code == 200
        assert stats.json()["sample_n"] >= 1


def test_notify_channel_and_test_without_network(monkeypatch):
    async def fake_dispatch(**kwargs):
        return [{"ok": True, "skipped": False}]

    monkeypatch.setattr("xianyu.routers.notify.dispatch_notify", fake_dispatch)
    with _client() as client:
        created = client.post(
            "/notify/channels",
            json={"name": "Bark", "kind": "bark", "endpoint": "testdevickey"},
        )
        assert created.status_code == 200
        assert "…" in created.json()["endpoint_masked"] or created.json()["endpoint_masked"]

        tested = client.post("/notify/test", json={"title": "t", "body": "b"})
        assert tested.status_code == 200


def test_ai_offline_chat():
    with _client() as client:
        res = client.post("/ai/chat", json={"message": "富士相机均价怎么样"})
        assert res.status_code == 200
        body = res.json()
        assert body["offline"] is True
        assert body["reply"]
        assert body["thread_id"]


def test_autoreply_rules_and_settings():
    with _client() as client:
        settings = client.put("/settings", json={"autoreply_mode": "draft"})
        assert settings.status_code == 200
        assert settings.json()["autoreply_mode"] == "draft"

        rule = client.post(
            "/autoreply/rules",
            json={"name": "在吗", "match_text": "还在", "reply_text": "在的"},
        )
        assert rule.status_code == 200
        rules = client.get("/autoreply/rules")
        assert rules.status_code == 200
        assert rules.json()["items"]


def test_workbench_index_available():
    with _client() as client:
        # Prefer built Vue dist; fall back to legacy web/
        home = client.get("/")
        assert home.status_code == 200
        assert "闲鱼工作台" in home.text or "app" in home.text.lower()
