import asyncio
import hashlib
import json
import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from tortoise import Model, fields
from tortoise.contrib.fastapi import register_tortoise

from api import (
    fetch_login_user,
    init,
    login_snapshot,
    login_with_cookie,
    logout,
    poll_qr_login,
    search,
    start_qr_login,
)
from im_service import im_service

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init()
    yield
    await im_service.stop()


# 初始化FastAPI应用
app = FastAPI(
    title="闲鱼 HTTP 接口",
    description="商品搜索 + Cookie/扫码登录 + 自动回复 + 消息通知（IM 使用官网同款 WebSocket）",
    lifespan=lifespan,
)


def get_md5(text: str) -> str:
    """返回给定文本的MD5哈希值"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def get_link_unique_key(link: str) -> str:
    """
    截取链接中前1个"&"之前的内容作为唯一标识依据。
    如果链接中的"&"少于1个，则返回整个链接。
    """
    # 尝试拆分链接，最多拆分1次
    parts = link.split('&', 1)
    if len(parts) >= 2:
        # 拼接前1部分，保留"&"连接符
        return '&'.join(parts[:1])
    else:
        return link


# 定义数据库模型，增加 link_hash 字段用于唯一性判断
class XianyuProduct(Model):
    id = fields.IntField(pk=True)
    title = fields.TextField(description="商品标题")
    price = fields.CharField(max_length=50, description="当前售价")
    area = fields.CharField(max_length=100, description="发货地区")
    seller = fields.CharField(max_length=100, description="卖家昵称")
    # 存储完整链接，不设置唯一性约束
    link = fields.TextField(description="商品链接", column_type="MEDIUMTEXT")
    # 使用 link_hash 字段保存截取后的链接 MD5 值，并设置唯一约束
    link_hash = fields.CharField(max_length=32, unique=True, description="商品链接哈希")
    image_url = fields.TextField(description="商品图片链接", column_type="MEDIUMTEXT")
    publish_time = fields.DatetimeField(null=True, description="发布时间")

    class Meta:
        table = "xianyu_products"


class ChatMessage(Model):
    id = fields.IntField(pk=True)
    conversation_id = fields.CharField(max_length=128, index=True, description="会话 ID")
    sender_id = fields.CharField(max_length=64, default="", description="发送者 ID")
    sender_name = fields.CharField(max_length=128, default="", description="发送者昵称")
    content = fields.TextField(description="消息内容")
    direction = fields.CharField(max_length=16, default="in", description="in/out")
    replied = fields.BooleanField(default=False, description="是否已自动回复")
    reply_text = fields.TextField(null=True, description="自动回复内容")
    raw_json = fields.TextField(null=True, description="原始推送")
    created_at = fields.DatetimeField(auto_now_add=True, description="入库时间")

    class Meta:
        table = "im_messages"


class ReplySetting(Model):
    id = fields.IntField(pk=True)
    enabled = fields.BooleanField(default=False, description="是否开启自动回复")
    default_reply = fields.TextField(default="您好，我看到消息后会尽快回复。")
    keywords_json = fields.TextField(default="[]", description="关键词回复 JSON")
    webhook_url = fields.CharField(max_length=500, default="", description="收到消息时回调的 URL")

    class Meta:
        table = "im_reply_settings"


class CookieLoginBody(BaseModel):
    cookie: str = Field(..., description="浏览器登录闲鱼后复制的完整 Cookie")


class KeywordReply(BaseModel):
    keyword: str
    reply: str


class AutoReplyBody(BaseModel):
    enabled: Optional[bool] = None
    default_reply: Optional[str] = None
    keyword_replies: Optional[list[KeywordReply]] = None
    webhook_url: Optional[str] = None


# 配置数据库
os.makedirs("data", exist_ok=True)
DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite://data/xianyu.sqlite3"
DATABASE_CONFIG = {
    "connections": {
        "default": DATABASE_URL
    },
    "apps": {
        "models": {
            "models": ["__main__"],
            "default_connection": "default",
        }
    }
}

register_tortoise(
    app,
    config=DATABASE_CONFIG,
    generate_schemas=True,  # 自动创建表结构
    add_exception_handlers=True,
)


async def safe_get(data, *keys, default="暂无"):
    """安全获取嵌套字典值"""
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError, IndexError):
            return default
    return data


async def save_to_db(data_list):
    """
    逐条保存数据到数据库，若相同链接（按截取规则判断）的记录已存在则跳过，
    同时统计当前关键词下新增的记录数量，并返回新增记录的 id 列表
    """
    new_records = 0
    new_ids = []
    for item in data_list:
        try:
            link = item["商品链接"]
            # 先截取链接内容
            unique_part = get_link_unique_key(link)
            # 计算唯一标识的 MD5 哈希值
            link_hash = get_md5(unique_part)
            product, created = await XianyuProduct.get_or_create(
                link_hash=link_hash,
                defaults={
                    "title": item["商品标题"],
                    "price": item["当前售价"],
                    "area": item["发货地区"],
                    "seller": item["卖家昵称"],
                    "link": link,
                    "image_url": item["商品图片链接"],
                    "publish_time": datetime.strptime(item["发布时间"], "%Y-%m-%d %H:%M")
                    if item["发布时间"] != "未知时间" else None,
                }
            )
            if created:
                new_records += 1
                new_ids.append(product.id)
        except Exception as e:
            print(f"保存数据出错: {str(e)}")
    return new_records, new_ids


async def handle_data(data: dict):
    if str(data).find("NoneOfResult") != -1:
        return []
    items = data.get("data", {}).get("resultList") or []
    res = []
    for item in items:
        main_data = await safe_get(item, "data", "item", "main", "exContent", default={})
        click_params = await safe_get(item, "data", "item", "main", "clickParam", "args", default={})

        # 解析商品信息
        title = await safe_get(main_data, "title", default="未知标题")

        # 价格处理
        price_parts = await safe_get(main_data, "price", default=[])
        price = "价格异常"
        if isinstance(price_parts, list):
            price = "".join([str(p.get("text", "")) for p in price_parts if isinstance(p, dict)])
            price = price.replace("当前价", "").strip()
            if "万" in price:
                price = f"¥{float(price.replace('¥', '').replace('万', '')) * 10000:.0f}"
        # 其他字段解析
        area = await safe_get(main_data, "area", default="地区未知")
        seller = await safe_get(main_data, "userNickName", default="匿名卖家")
        raw_link = await safe_get(item, "data", "item", "main", "targetUrl", default="")
        image_url = await safe_get(main_data, "picUrl", default="")

        res.append({
            "商品标题": title,
            "当前售价": price,
            "发货地区": area,
            "卖家昵称": seller,
            "商品链接": raw_link.replace("fleamarket://", "https://www.goofish.com/"),
            "商品图片链接": f"https:{image_url}" if image_url and not image_url.startswith(
                "http") else image_url,
            "发布时间": datetime.fromtimestamp(
                int(click_params.get("publishTime", 0)) / 1000
            ).strftime("%Y-%m-%d %H:%M") if click_params.get("publishTime", "").isdigit() else "未知时间"
        })
    return res


async def scrape_xianyu_http(keyword: str, max_pages: int = 1):
    semaphore = asyncio.Semaphore(3)

    async def fetch_page(page: int):
        async with semaphore:
            return page, await handle_data(await search(keyword, page))

    gathered = await asyncio.gather(*[fetch_page(page) for page in range(1, max_pages + 1)])
    res = []
    for _, items in sorted(gathered, key=lambda item: item[0]):
        res.extend(items)
    return res


@app.post("/search/", summary="商品搜索接口",
          description="接收搜索关键词和页数，返回爬取结果数量、新增记录数量及新增记录的id列表")
async def search_items(keyword: str, max_pages: int = 1):
    """
    参数：
    - keyword: 搜索关键词（必需）
    - max_pages: 最大爬取页数（默认1）
    """
    try:
        data_list = await scrape_xianyu_http(keyword, max_pages)

        # 保存数据并统计新增记录数，同时返回新增记录的id列表
        new_count, new_ids = (0, [])
        if data_list:
            new_count, new_ids = await save_to_db(data_list)

        return {
            "status": "success",
            "keyword": keyword,
            "total_results": len(data_list),
            "new_records": new_count,
            "new_record_ids": new_ids
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"爬取失败: {str(e)}")


async def _reply_setting() -> ReplySetting:
    setting = await ReplySetting.get_or_none(id=1)
    if setting is None:
        setting = await ReplySetting.create(id=1)
    return setting


def _setting_payload(setting: ReplySetting) -> dict:
    try:
        keywords = json.loads(setting.keywords_json or "[]")
    except json.JSONDecodeError:
        keywords = []
    return {
        "enabled": setting.enabled,
        "default_reply": setting.default_reply,
        "keyword_replies": keywords,
        "webhook_url": setting.webhook_url,
    }


@app.post("/auth/cookie", summary="Cookie 登录")
async def auth_cookie(body: CookieLoginBody):
    try:
        return await login_with_cookie(body.cookie)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"登录失败: {exc}") from exc


@app.post("/auth/qr/start", summary="生成闲鱼扫码登录二维码")
async def auth_qr_start():
    try:
        return await start_qr_login()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"二维码生成失败: {exc}") from exc


@app.get("/auth/qr/status", summary="查询扫码登录状态")
async def auth_qr_status(session_id: str = Query(..., description="start 接口返回的 session_id")):
    try:
        return await poll_qr_login(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"查询扫码状态失败: {exc}") from exc


@app.get("/auth/status", summary="当前登录态")
async def auth_status():
    snapshot = login_snapshot()
    if snapshot.get("logged_in"):
        try:
            snapshot["user"] = await fetch_login_user()
        except Exception as exc:
            snapshot["warning"] = str(exc)
    return snapshot


@app.post("/auth/logout", summary="退出登录")
async def auth_logout():
    await im_service.stop()
    logout()
    return {"ok": True}


@app.get("/im/config", summary="读取自动回复配置")
async def get_im_config():
    return _setting_payload(await _reply_setting())


@app.put("/im/config", summary="更新自动回复与 Webhook 通知")
async def put_im_config(body: AutoReplyBody):
    setting = await _reply_setting()
    if body.enabled is not None:
        setting.enabled = body.enabled
    if body.default_reply is not None:
        setting.default_reply = body.default_reply
    if body.keyword_replies is not None:
        setting.keywords_json = json.dumps(
            [item.model_dump() for item in body.keyword_replies],
            ensure_ascii=False,
        )
    if body.webhook_url is not None:
        setting.webhook_url = body.webhook_url
    await setting.save()
    return _setting_payload(setting)


@app.post("/im/start", summary="开始监听消息并自动回复")
async def im_start():
    snapshot = login_snapshot()
    if not snapshot.get("logged_in"):
        raise HTTPException(status_code=401, detail="请先通过 /auth/cookie 或扫码登录")
    return await im_service.start()


@app.post("/im/stop", summary="停止监听")
async def im_stop():
    return await im_service.stop()


@app.get("/im/status", summary="IM 监听状态")
async def im_status():
    return im_service.status() | {"login": login_snapshot()}


@app.get("/im/messages", summary="最近收到的消息")
async def im_messages(limit: int = Query(50, ge=1, le=200)):
    rows = await ChatMessage.all().order_by("-id").limit(limit)
    return [
        {
            "id": row.id,
            "conversation_id": row.conversation_id,
            "sender_id": row.sender_id,
            "sender_name": row.sender_name,
            "content": row.content,
            "direction": row.direction,
            "replied": row.replied,
            "reply_text": row.reply_text,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@app.get("/im/events", summary="SSE 实时通知（收到消息/已回复）")
async def im_events():
    queue = im_service.subscribe()

    async def generate():
        try:
            yield 'data: {"event":"connected"}\n\n'
            while True:
                item = await queue.get()
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        finally:
            im_service.unsubscribe(queue)

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
