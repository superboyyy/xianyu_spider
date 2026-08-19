"""启动入口：python spider.py [serve|login]"""

from xianyu.app import app


def main(argv: list[str] | None = None) -> None:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="闲鱼 HTTP 接口")
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["serve", "login"],
        help="serve 启动 API；login 在终端显示二维码并扫码登录",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.command == "login":
        from xianyu.cli import run_qr_login

        raise SystemExit(asyncio.run(run_qr_login()))

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
