"""闲鱼 IM WebSocket 客户端（LWP JSON）。"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any, AsyncIterator, Optional

import websockets

from xianyu.im_protocol import (
    extract_incoming_message,
    generate_mid,
    generate_uuid,
    iter_sync_packages,
)
from xianyu.mtop import IM_APP_KEY, cookie_header, fetch_im_token

logger = logging.getLogger(__name__)

WS_URL = "wss://wss-goofish.dingtalk.com/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 DingTalk(2.1.5) "
    "OS(Windows/10) Browser(Chrome/120.0.0.0) DingWeb/2.1.5 IMPaaS DingWeb/2.1.5"
)


class GoofishIMClient:
    def __init__(self) -> None:
        self.ws = None
        self.access_token = ""
        self.device_id = ""
        self.user_id = ""
        self.connected = False
        self._incoming: asyncio.Queue = asyncio.Queue()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reader_task: Optional[asyncio.Task] = None

    async def connect(self) -> dict:
        token_info = await fetch_im_token()
        self.access_token = token_info["access_token"]
        self.device_id = token_info["device_id"]
        self.user_id = token_info["user_id"]
        if not self.access_token:
            raise RuntimeError("IM accessToken 为空，请确认已登录")
        headers = {
            "Cookie": cookie_header(),
            "User-Agent": UA,
            "Origin": "https://www.goofish.com",
        }
        try:
            self.ws = await websockets.connect(
                WS_URL, additional_headers=headers, ping_interval=None
            )
        except TypeError:
            self.ws = await websockets.connect(
                WS_URL, extra_headers=headers, ping_interval=None
            )
        self.connected = True
        self._reader_task = asyncio.create_task(self._read_loop())
        await self._register()
        await self._ack_diff()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        return token_info

    async def close(self) -> None:
        self.connected = False
        for task in (self._heartbeat_task, self._reader_task):
            if task:
                task.cancel()
        self._heartbeat_task = None
        self._reader_task = None
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
        try:
            self._incoming.put_nowait(None)
        except Exception:
            pass

    async def send_text(self, conversation_id: str, to_user_id: str, text: str) -> None:
        cid = conversation_id if "@" in conversation_id else f"{conversation_id}@goofish"
        self_id = self.user_id
        payload = {"contentType": 1, "text": {"text": text}}
        encoded = base64.b64encode(
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        body = [
            {
                "uuid": generate_uuid(),
                "cid": cid,
                "conversationType": 1,
                "content": {
                    "contentType": 101,
                    "custom": {"type": 1, "data": encoded},
                },
                "redPointPolicy": 0,
                "extension": {"extJson": "{}"},
                "ctx": {"appVersion": "1.0", "platform": "web"},
                "mtags": {},
                "msgReadStatusSetting": 1,
            },
            {
                "actualReceivers": [
                    f"{to_user_id}@goofish",
                    f"{self_id}@goofish",
                ]
            },
        ]
        await self._send_lwp("/r/MessageSend/sendByReceiverScope", body)

    async def messages(self) -> AsyncIterator[dict[str, str]]:
        while self.connected or not self._incoming.empty():
            item = await self._incoming.get()
            if item is None:
                return
            yield item

    async def _register(self) -> None:
        headers = {
            "cache-header": "app-key token ua wv",
            "app-key": IM_APP_KEY,
            "token": self.access_token,
            "ua": UA,
            "dt": "j",
            "wv": "im:3,au:3,sy:6",
            "sync": "0,0;0;0;",
            "did": self.device_id,
        }
        await self._send_lwp("/reg", headers=headers)

    async def _ack_diff(self) -> None:
        now = int(time.time() * 1000)
        body = [
            {
                "pipeline": "sync",
                "tooLong2Tag": "PNM,1",
                "channel": "sync",
                "topic": "sync",
                "highPts": 0,
                "pts": now * 1000,
                "seq": 0,
                "timestamp": now,
            }
        ]
        await self._send_lwp("/r/SyncStatus/ackDiff", body)

    async def _heartbeat_loop(self) -> None:
        while self.connected:
            try:
                await self._send_lwp("/!")
            except Exception as exc:
                logger.warning("IM 心跳失败: %s", exc)
                return
            await asyncio.sleep(15)

    async def _send_lwp(self, lwp: str, body: Any = None, headers: Optional[dict] = None) -> str:
        if self.ws is None:
            raise RuntimeError("IM 未连接")
        mid = generate_mid()
        message = {"lwp": lwp, "headers": {"mid": mid, **(headers or {})}}
        if body is not None:
            message["body"] = body
        await self.ws.send(json.dumps(message, ensure_ascii=False, separators=(",", ":")))
        return mid

    async def _read_loop(self) -> None:
        assert self.ws is not None
        try:
            async for raw in self.ws:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._ack(message)
                lwp = str(message.get("lwp") or "")
                dumped = json.dumps(message, ensure_ascii=False)
                if lwp in {"/s/sync", "/s/pre"} or "syncPushPackage" in dumped:
                    await self._handle_sync(message)
        except Exception as exc:
            logger.warning("IM 读取中断: %s", exc)
            self.connected = False
            try:
                self._incoming.put_nowait(None)
            except Exception:
                pass

    async def _ack(self, message: dict) -> None:
        headers = message.get("headers") or {}
        if not headers or self.ws is None:
            return
        ack = {
            "code": 200,
            "headers": {
                "mid": headers.get("mid") or generate_mid(),
                "sid": headers.get("sid") or "",
            },
        }
        for key in ("app-key", "ua", "dt"):
            if key in headers:
                ack["headers"][key] = headers[key]
        await self.ws.send(json.dumps(ack, ensure_ascii=False, separators=(",", ":")))

    async def _handle_sync(self, message: dict) -> None:
        for package in iter_sync_packages(message):
            incoming = extract_incoming_message(package)
            if incoming and incoming.get("text"):
                await self._incoming.put(incoming)
        fallback = extract_incoming_message(message.get("body"))
        if fallback and fallback.get("text"):
            await self._incoming.put(fallback)
