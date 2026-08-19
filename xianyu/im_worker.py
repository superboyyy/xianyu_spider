"""自动回复与消息通知：挂在 IM 长连接上，对外提供 HTTP/SSE/Webhook。"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

import httpx

from xianyu.im_client import GoofishIMClient
from xianyu.protocol import is_system_sender, match_auto_reply, render_reply

logger = logging.getLogger(__name__)


class IMService:
    def __init__(self) -> None:
        self.client: Optional[GoofishIMClient] = None
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.last_error = ""
        self._subscribers: list[asyncio.Queue] = []
        self._seen: set[str] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def start(self) -> dict:
        if self.running:
            return self.status()
        self.running = True
        self.last_error = ""
        self.task = asyncio.create_task(self._run())
        return self.status()

    async def stop(self) -> dict:
        self.running = False
        if self.client:
            await self.client.close()
            self.client = None
        if self.task:
            self.task.cancel()
            self.task = None
        return self.status()

    def status(self) -> dict:
        return {
            "running": self.running,
            "connected": bool(self.client and self.client.connected),
            "user_id": getattr(self.client, "user_id", "") if self.client else "",
            "last_error": self.last_error,
            "subscribers": len(self._subscribers),
        }

    async def _run(self) -> None:
        while self.running:
            im = GoofishIMClient()
            self.client = im
            try:
                await im.connect()
                self.last_error = ""
                async for incoming in im.messages():
                    if not self.running:
                        break
                    await self._handle_incoming(incoming)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("IM 监听异常")
            finally:
                await im.close()
                if self.client is im:
                    self.client = None
            if self.running:
                await asyncio.sleep(3)

    async def _handle_incoming(self, incoming: dict) -> None:
        from xianyu.models import ChatMessage, ReplySetting

        text = (incoming.get("text") or "").strip()
        sender_id = incoming.get("sender_id") or ""
        sender_name = incoming.get("sender_name") or ""
        conversation_id = incoming.get("conversation_id") or ""
        if not text:
            return
        fingerprint = f"{conversation_id}:{sender_id}:{text}"
        if fingerprint in self._seen:
            return
        self._seen.add(fingerprint)
        if len(self._seen) > 5000:
            self._seen = set(list(self._seen)[-2000:])

        my_id = getattr(self.client, "user_id", "") if self.client else ""
        outbound = bool(my_id and sender_id and sender_id == my_id)
        record = await ChatMessage.create(
            conversation_id=conversation_id or "unknown",
            sender_id=sender_id,
            sender_name=sender_name,
            content=text,
            direction="out" if outbound else "in",
            replied=False,
            reply_text=None,
            raw_json=json.dumps(incoming, ensure_ascii=False),
        )

        event = {
            "event": "message.received",
            "id": record.id,
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "text": text,
            "direction": record.direction,
            "created_at": datetime.utcnow().isoformat(),
        }
        await self._publish(event)

        setting = await ReplySetting.get_or_none(id=1) or await ReplySetting.create(id=1)
        if outbound or not setting.enabled:
            return
        if is_system_sender(sender_name, text):
            return
        if my_id and sender_id and sender_id == my_id:
            return

        try:
            keywords = json.loads(setting.keywords_json or "[]")
        except json.JSONDecodeError:
            keywords = []
        reply = match_auto_reply(text, setting.default_reply, keywords)
        if not reply:
            return
        reply = render_reply(reply, incoming)
        if self.client and conversation_id and sender_id:
            try:
                await self.client.send_text(conversation_id, sender_id, reply)
                record.replied = True
                record.reply_text = reply
                await record.save()
                await self._publish(
                    {
                        "event": "message.replied",
                        "id": record.id,
                        "conversation_id": conversation_id,
                        "sender_id": sender_id,
                        "text": text,
                        "reply": reply,
                    }
                )
            except Exception as exc:
                logger.exception("自动回复失败")
                self.last_error = f"自动回复失败: {exc}"

        if setting.webhook_url:
            await self._post_webhook(setting.webhook_url, event | {"reply": record.reply_text})

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

    async def _post_webhook(self, url: str, event: dict) -> None:
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                await http.post(url, json=event)
        except Exception as exc:
            logger.warning("Webhook 通知失败: %s", exc)


im_service = IMService()
