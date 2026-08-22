from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from tortoise.contrib.fastapi import register_tortoise

from xianyu.config import DATABASE_URL
from xianyu.mtop import init as init_goofish
from xianyu.routers import auth, im, search

load_dotenv()


def create_app(*, connect_xianyu: bool = True, db_url: str | None = None) -> FastAPI:
    """组装 FastAPI 应用。测试时可关闭闲鱼初始化，避免打真实网络。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if connect_xianyu:
            await init_goofish()
        try:
            yield
        finally:
            from xianyu.im_service import im_service

            await im_service.stop()

    app = FastAPI(
        title="闲鱼 HTTP 接口",
        description="商品搜索 + Cookie/扫码登录 + 闲鱼私信",
        lifespan=lifespan,
    )
    app.include_router(search.router)
    app.include_router(auth.router)
    app.include_router(im.router)

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
