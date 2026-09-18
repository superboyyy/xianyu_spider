from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from xianyu.config import DATABASE_URL
from xianyu.mtop import init as init_goofish
from xianyu.routers import ai, auth, autoreply, im, notify, products, search, watches

load_dotenv()


def create_app(*, connect_xianyu: bool = True, db_url: str | None = None) -> FastAPI:
    """组装 FastAPI 应用。测试时可关闭闲鱼初始化，避免打真实网络。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from xianyu.models import ensure_im_schema
        from xianyu.watch.scheduler import scheduler

        await ensure_im_schema()
        if connect_xianyu:
            await init_goofish()
            await scheduler.start()
        try:
            yield
        finally:
            from xianyu.im_service import im_service

            await scheduler.stop()
            await im_service.stop()

    app = FastAPI(
        title="闲鱼工作台",
        description="本机 API：搜货、货架、盯盘、AI、私信、通知。",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(search.router)
    app.include_router(auth.router)
    app.include_router(im.router)
    app.include_router(products.router)
    app.include_router(watches.router)
    app.include_router(notify.router)
    app.include_router(ai.router)
    app.include_router(autoreply.router)

    register_tortoise(
        app,
        config={
            "connections": {"default": db_url or DATABASE_URL},
            "apps": {
                "models": {
                    "models": ["xianyu.models"],
                    "default_connection": "default",
                }
            },
        },
        generate_schemas=True,
        add_exception_handlers=True,
    )
    return app


app = create_app()
