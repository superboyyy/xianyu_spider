"""启动入口：python spider.py"""

from xianyu.app import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
