"""闲鱼 IM WebSocket 客户端（LWP JSON）。

登录与 Token 走 HTTP mtop；消息收发与官网一致，必须维持这条长连接。
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, AsyncIterator, Callable, Optional

import websockets

from xianyu.mtop import IM_APP_KEY, client, current_cookies, fetch_im_token
from xianyu.protocol import (
    extract_incoming_message,
    generate_mid,
    generate_uuid,
    iter_sync_packages,
    parse_cookie_header,
)

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
        self._pending: dict[str, asyncio.Future] = {}
        self._incoming: asyncio.Queue = asyncio.Queue()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reader_task: Optional[asyncio.Task] = None
        self.connected = False

    async def connect(self) -> dict:
        token_info = await fetch_im_token()
        self.access_token = token_info["access_token"]
        self.device_id = token_info["device_id"]
        self.user_id = token_info["user_id"]
        if not self.access_token:
            raise RuntimeError("IM accessToken 为空，请确认已登录")
        headers = {
            "Cookie": dump_cookie_from_client(),
            "User-Agent": UA,
            "Origin": "https://www.goofish.com",
        }
        try:
            self.ws = await websockets.connect(WS_URL, additional_headers=headers, ping_interval=None)
        except TypeError:
            self.ws = await websockets.connect(WS_URL, extra_headers=headers, ping_interval=None)
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
            await self.ws.close()
            self.ws = None
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

    async def send_text(self, conversation_id: str, to_user_id: str, text: str) -> None:
        cid = conversation_id if "@" in conversation_id else f"{conversation_id}@goofish"
        self_id = self.user_id
        payload = {
            "contentType": 1,
            "text": {"text": text},
        }
        encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
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
        while self.connected:
            item = await self._incoming.get()
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
        now = int(time_ms())
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
                lwp = message.get("lwp") or ""
                if lwp in {"/s/sync", "/s/pre"} or "syncPushPackage" in json.dumps(message, ensure_ascii=False):
                    await self._handle_sync(message)
        except Exception as exc:
            logger.warning("IM 读取中断: %s", exc)
            self.connected = False

    async def _ack(self, message: dict) -> None:
        headers = message.get("headers") or {}
        if not headers:
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
        if self.ws is not None:
            await self.ws.send(json.dumps(ack, ensure_ascii=False, separators=(",", ":")))

    async def _handle_sync(self, message: dict) -> None:
        for package in iter_sync_packages(message):
            incoming = extract_incoming_message(package)
            if incoming and incoming.get("text"):
                await self._incoming.put(incoming)
        # 有些推送把正文直接放在 body 里
        fallback = extract_incoming_message(message.get("body"))
        if fallback and fallback.get("text"):
            await self._incoming.put(fallback)


def dump_cookie_from_client() -> str:
    cookies = current_cookies()
    if cookies:
        from xianyu.protocol import dump_cookie_header

        return dump_cookie_header(cookies)
    header = ""
    try:
        header = "; ".join(f"{k}={v}" for k, v in client.cookies.items())
    except Exception:
        header = ""
    return header


def time_ms() -> int:
    import time

    return int(time.time() * 1000)
