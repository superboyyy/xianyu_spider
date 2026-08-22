import asyncio
import time

from fastapi.testclient import TestClient

from xianyu.app import create_app
from xianyu.im_client import GoofishIMClient
from xianyu.im_service import im_service
from xianyu.mtop import apply_cookies, logout


def _client():
    app = create_app(connect_xianyu=False, db_url="sqlite://:memory:")
    return TestClient(app)


class FakeIM:
    def __init__(self):
        self.user_id = "1"
        self.connected = False
        self.sent = []
        self._queue: asyncio.Queue = asyncio.Queue()

    async def connect(self):
        self.connected = True
        return {"access_token": "tok", "device_id": "dev", "user_id": "1"}

    async def close(self):
        self.connected = False
        await self._queue.put(None)

    async def send_text(self, conversation_id, to_user_id, text):
        self.sent.append((conversation_id, to_user_id, text))

    async def messages(self):
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item


def test_im_start_requires_login():
    logout()
    with _client() as client:
        res = client.post("/im/start")
        assert res.status_code == 401


def test_im_send_without_start_is_conflict(monkeypatch):
    async def fake_login():
        return {"logged_in": True, "user_id": "1"}

    monkeypatch.setattr("xianyu.routers.im.require_login", fake_login)
    logout()
    apply_cookies("unb=1; cookie2=abc")
    with _client() as client:
        res = client.post(
            "/im/send",
            json={"conversation_id": "2", "to_user_id": "2", "text": "hi"},
        )
        assert res.status_code == 409
    logout()


def test_im_start_send_and_history(monkeypatch):
    fake = FakeIM()

    async def fake_login():
        return {"logged_in": True, "user_id": "1"}

    monkeypatch.setattr("xianyu.routers.im.require_login", fake_login)
    im_service.client_factory = lambda: fake
    logout()
    apply_cookies("unb=1; cookie2=abc")
    try:
        with _client() as client:
            started = client.post("/im/start")
            assert started.status_code == 200
            body = started.json()
            assert body["running"] is True
            assert body["connected"] is True
            assert "ws_frames" in body
            assert "sync_pushes" in body
            assert "parsed" in body
            assert "last_lwp" in body
            assert "last_decode_error" in body

            sent = client.post(
                "/im/send",
                json={
                    "conversation_id": "99@goofish",
                    "to_user_id": "99",
                    "text": "在的",
                    "source": "user",
                },
            )
            assert sent.status_code == 200
            assert sent.json()["direction"] == "out"
            assert sent.json()["text"] == "在的"
            assert fake.sent == [("99", "99", "在的")]

            fake._queue.put_nowait({
                "conversation_id": "99",
                "sender_id": "99",
                "sender_name": "买家",
                "text": "还在吗",
            })

            messages = None
            for _ in range(30):
                messages = client.get("/im/messages", params={"conversation_id": "99"})
                if any(item["text"] == "还在吗" for item in messages.json()):
                    break
                time.sleep(0.05)
            assert messages.status_code == 200
            texts = [item["text"] for item in messages.json()]
            assert "在的" in texts
            assert "还在吗" in texts

            conv = client.get("/im/conversations")
            assert conv.status_code == 200
            assert any(item["conversation_id"] == "99" for item in conv.json())

            stopped = client.post("/im/stop")
            assert stopped.status_code == 200
            assert stopped.json()["running"] is False
    finally:
        im_service.client_factory = GoofishIMClient
        logout()
