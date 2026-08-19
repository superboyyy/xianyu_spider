from fastapi.testclient import TestClient

from spider import app


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
