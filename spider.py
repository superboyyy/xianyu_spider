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
        help="serve 启动 API；login 先画登录码，需要核身时再开浏览器（也可用 --cookie / --browser）",
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
        help="与默认 login 相同：终端画登录码（兼容旧参数）",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="直接打开官方登录页扫码，不先画终端码",
    )
    parser.add_argument("--timeout", type=int, default=180, help="拍脸/官方页扫码等待秒数")
    args = parser.parse_args(argv)
    if args.command == "login":
        from xianyu.cli import run_login

        if args.cookie is not None:
            mode = "cookie"
        elif args.browser:
            mode = "browser"
        else:
            mode = "qr"
        raise SystemExit(
            asyncio.run(
                run_login(mode=mode, cookie=args.cookie or "", timeout=args.timeout)
            )
        )

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
