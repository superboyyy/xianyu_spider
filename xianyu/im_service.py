"""IM 长连接管家：收发、入库、SSE。不接 webhook / 自动回复。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional

from xianyu.im_client import GoofishIMClient
from xianyu.models import ChatMessage

logger = logging.getLogger(__name__)

ClientFactory = Callable[[], Any]


def _row_payload(row: ChatMessage) -> dict[str, Any]:
    created = row.created_at.isoformat() if row.created_at else None
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "sender_id": row.sender_id,
        "sender_name": row.sender_name,
        "text": row.text,
        "direction": row.direction,
        "source": row.source,
        "created_at": created,
    }


class IMService:
    def __init__(self) -> None:
        self.client_factory: ClientFactory = GoofishIMClient
        self.client: Optional[Any] = None
        self.running = False
        self.connected = False
        self.user_id = ""
        self.last_error = ""
        self._task: Optional[asyncio.Task] = None
        self._subscribers: list[asyncio.Queue] = []
        self._seen: set[str] = set()

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "connected": bool(self.connected and self.client),
            "user_id": self.user_id,
            "last_error": self.last_error,
            "subscribers": len(self._subscribers),
        }

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def start(self) -> dict[str, Any]:
        if self.running:
            return self.status()
        self.running = True
        self.last_error = ""
        self._task = asyncio.create_task(self._run())
        for _ in range(40):
            if self.connected or self.last_error or not self.running:
                break
            await asyncio.sleep(0.05)
        return self.status()

    async def stop(self) -> dict[str, Any]:
        self.running = False
        if self.client is not None:
            try:
                await self.client.close()
            except Exception:
                pass
            self.client = None
        self.connected = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        return self.status()

    async def send_text(
        self,
        *,
        conversation_id: str,
        to_user_id: str,
        text: str,
        source: str = "user",
    ) -> dict[str, Any]:
        content = (text or "").strip()
        if not content:
            raise ValueError("text 不能为空")
        if not self.connected or self.client is None:
            raise RuntimeError("IM 未连接，请先 POST /im/start")
        cid = (conversation_id or "").split("@", 1)[0]
        await self.client.send_text(cid, to_user_id, content)
        row = await self._store(
            {
                "conversation_id": cid,
                "sender_id": self.user_id,
                "sender_name": "",
                "text": content,
            },
            direction="out",
            source=source or "user",
        )
        payload = _row_payload(row)
        await self._publish({"event": "message.sent", **payload})
        return payload

    async def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = await ChatMessage.all().order_by("-id")
        seen: dict[str, ChatMessage] = {}
        for row in rows:
            if row.conversation_id in seen:
                continue
            seen[row.conversation_id] = row
            if len(seen) >= limit:
                break
        return [_row_payload(row) for row in seen.values()]

    async def list_messages(
        self, conversation_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = ChatMessage.all().order_by("-id").limit(limit)
        if conversation_id:
            cid = conversation_id.split("@", 1)[0]
            query = ChatMessage.filter(conversation_id=cid).order_by("-id").limit(limit)
        rows = await query
        return [_row_payload(row) for row in reversed(list(rows))]

    async def _run(self) -> None:
        while self.running:
            im = self.client_factory()
            self.client = im
            try:
                info = await im.connect()
                self.user_id = str(info.get("user_id") or getattr(im, "user_id", "") or "")
                self.connected = True
                self.last_error = ""
                async for incoming in im.messages():
                    if not self.running:
                        break
                    await self._on_incoming(incoming)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("IM 连接中断")
                self.last_error = str(exc)
                self.connected = False
                if self.running:
                    await asyncio.sleep(3)
            finally:
                self.connected = False
                if self.client is im:
                    try:
                        await im.close()
                    except Exception:
                        pass
                    self.client = None

    async def _on_incoming(self, incoming: dict) -> None:
        text = str(incoming.get("text") or "").strip()
        if not text:
            return
        cid = str(incoming.get("conversation_id") or "").split("@", 1)[0]
        sender = str(incoming.get("sender_id") or "")
        fingerprint = f"{cid}:{sender}:{text}"
        if fingerprint in self._seen:
            return
        self._seen.add(fingerprint)
        if len(self._seen) > 5000:
            self._seen = set(list(self._seen)[-2000:])
        direction = "out" if self.user_id and sender == self.user_id else "in"
        row = await self._store(
            {
                "conversation_id": cid,
                "sender_id": sender,
                "sender_name": str(incoming.get("sender_name") or ""),
                "text": text,
            },
            direction=direction,
            source="gateway",
        )
        await self._publish({"event": "message.received", **_row_payload(row)})

    async def _store(self, incoming: dict, *, direction: str, source: str) -> ChatMessage:
        return await ChatMessage.create(
            conversation_id=str(incoming.get("conversation_id") or ""),
            sender_id=str(incoming.get("sender_id") or ""),
            sender_name=str(incoming.get("sender_name") or ""),
            text=str(incoming.get("text") or ""),
            direction=direction,
            source=source,
            raw_json=json.dumps(incoming, ensure_ascii=False),
        )

    async def _publish(self, event: dict) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except Exception:
                    pass
                try:
                    queue.put_nowait(event)
                except Exception:
                    pass


im_service = IMService()
