from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tortoise.contrib.fastapi import register_tortoise

from xianyu.config import DATABASE_URL, ROOT_DIR
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
        description="本机客户端：搜货、货架、盯盘、AI、私信、通知。打开 / 即是工作台。",
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

    web_dir = Path(ROOT_DIR) / "web"
    dist_dir = Path(ROOT_DIR) / "frontend" / "dist"
    static_root = dist_dir if dist_dir.is_dir() else web_dir
    if static_root.is_dir():
        assets = static_root / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/")
        async def spa_index():
            return FileResponse(static_root / "index.html")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            candidate = static_root / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            index = static_root / "index.html"
            if index.is_file() and not full_path.startswith(
                ("auth", "im", "search", "products", "watches", "notify", "ai", "autoreply", "settings", "docs", "openapi")
            ):
                return FileResponse(index)
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Not Found")

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
