import os

import pytest


@pytest.mark.skipif(not os.getenv("RUN_LIVE"), reason="默认跳过真实闲鱼网络。RUN_LIVE=1 时执行")
def test_live_search_returns_items():
    import asyncio

    from xianyu.mtop import init, search

    async def run():
        await init()
        result = await search("手机", 1)
        assert any(str(item).startswith("SUCCESS") for item in (result.get("ret") or []))
        items = (result.get("data") or {}).get("resultList") or []
        assert len(items) > 0

    asyncio.run(run())
