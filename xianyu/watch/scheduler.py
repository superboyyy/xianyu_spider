"""进程内盯盘调度。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from xianyu.models import Watch
from xianyu.watch.runner import run_watch

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WatchScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self._tick_seconds = 30

    def status(self) -> dict:
        return {"running": self._running, "tick_seconds": self._tick_seconds}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except Exception:
                logger.exception("盯盘调度异常")
            await asyncio.sleep(self._tick_seconds)

    async def _tick(self) -> None:
        now = _utcnow()
        watches = await Watch.filter(enabled=True)
        for watch in watches:
            interval = max(1, int(watch.interval_minutes or 15))
            due = watch.last_run_at is None or watch.last_run_at <= now - timedelta(minutes=interval)
            if not due:
                continue
            try:
                await run_watch(watch.id)
            except Exception:
                logger.exception("自动盯盘失败 id=%s", watch.id)


scheduler = WatchScheduler()
