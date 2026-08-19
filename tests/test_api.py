from uuid import uuid4

from fastapi.testclient import TestClient

from spider import app


SAMPLE_PRODUCT = {
    "商品标题": "测试手机",
    "当前售价": "¥99",
    "发货地区": "上海",
    "卖家昵称": "卖家A",
    "商品链接": "https://www.goofish.com/item?id=demo-1",
    "商品图片链接": "https://img.alicdn.com/test.jpg",
    "发布时间": "2026-01-01 12:00",
}


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_search_openapi_uses_json_body():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        post = schema["paths"]["/search/"]["post"]
        assert "requestBody" in post
        assert "keyword" not in [p.get("name") for p in post.get("parameters") or []]


def test_search_rejects_empty_keyword():
    with TestClient(app) as client:
        response = client.post("/search/", json={"keyword": "", "max_pages": 1})
        assert response.status_code == 422


def test_search_returns_product_items(monkeypatch):
    sample = {
        **SAMPLE_PRODUCT,
        "商品链接": f"https://www.goofish.com/item?id=demo-{uuid4().hex}",
    }

    async def fake_scrape(keyword, max_pages=1):
        return [sample]

    monkeypatch.setattr("spider.scrape_xianyu", fake_scrape)
    with TestClient(app) as client:
        response = client.post("/search/", json={"keyword": "手机", "max_pages": 1})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["keyword"] == "手机"
        assert body["total_results"] == 1
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert item["title"] == "测试手机"
        assert item["price"] == "¥99"
        assert item["area"] == "上海"
        assert item["seller"] == "卖家A"
        assert item["link"] == sample["商品链接"]
        assert item["image_url"] == sample["商品图片链接"]
        assert item["publish_time"] == "2026-01-01 12:00"
        assert item["id"] is not None
        assert item["is_new"] is True
        assert body["new_records"] == 1
        assert body["new_record_ids"] == [item["id"]]
