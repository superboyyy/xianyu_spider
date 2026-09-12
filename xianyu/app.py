from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from tortoise.contrib.fastapi import register_tortoise

from xianyu.config import DATABASE_URL, ROOT_DIR
from xianyu.mtop import init as init_goofish
from xianyu.routers import auth, im, products, search

load_dotenv()


def create_app(*, connect_xianyu: bool = True, db_url: str | None = None) -> FastAPI:
    """组装 FastAPI 应用。测试时可关闭闲鱼初始化，避免打真实网络。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from xianyu.models import ensure_im_schema

        await ensure_im_schema()
        if connect_xianyu:
            await init_goofish()
        try:
            yield
        finally:
            from xianyu.im_service import im_service

            await im_service.stop()

    app = FastAPI(
        title="闲鱼工作台",
        description="本机客户端：搜索、货架、登录、私信。打开 / 即是工作台。",
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
    web_dir = Path(ROOT_DIR) / "web"
    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

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
