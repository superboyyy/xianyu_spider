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
        help="serve 启动 API；login 打开官方登录页扫码（也可用 --cookie / --http）",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--cookie",
        nargs="?",
        const="-",
        default=None,
        help="粘贴网页 Cookie 登录；不跟值则从终端读入",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="终端画码纯 HTTP 登录（常被拍脸拦住，不推荐）",
    )
    parser.add_argument("--timeout", type=int, default=180, help="浏览器扫码等待秒数")
    args = parser.parse_args(argv)
    if args.command == "login":
        from xianyu.cli import run_login

        mode = "cookie" if args.cookie is not None else ("http" if args.http else "browser")
        raise SystemExit(
            asyncio.run(
                run_login(mode=mode, cookie=args.cookie or "", timeout=args.timeout)
            )
        )

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
