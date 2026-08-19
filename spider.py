import asyncio
import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from playwright.async_api import Page, async_playwright
from pydantic import BaseModel, Field
from tortoise.contrib.fastapi import register_tortoise

from models import XianyuProduct

load_dotenv()

app = FastAPI(title="闲鱼商品搜索API", description="支持并发请求的闲鱼商品搜索接口")

SEARCH_API_MARK = "/mtop.taobao.idlemtopsearch.pc.search/1.0"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class SearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    max_pages: int = Field(1, ge=1, le=20, description="最大爬取页数")


def get_md5(text: str) -> str:
    """返回给定文本的MD5哈希值"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def get_link_unique_key(link: str) -> str:
    """截取链接中第一个 '&' 之前的内容作为唯一标识。"""
    return link.split("&", 1)[0]


def safe_get(data: Any, *keys: Any, default: Any = "暂无") -> Any:
    """安全获取嵌套字典值"""
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError, IndexError):
            return default
    return data


def parse_product_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """把闲鱼搜索 API 的单条结果解析成存储结构。"""
    main_data = safe_get(item, "data", "item", "main", "exContent", default={})
    click_params = safe_get(item, "data", "item", "main", "clickParam", "args", default={})
    if not isinstance(main_data, dict):
        main_data = {}
    if not isinstance(click_params, dict):
        click_params = {}

    title = safe_get(main_data, "title", default="未知标题")
    price_parts = safe_get(main_data, "price", default=[])
    price = "价格异常"
    if isinstance(price_parts, list):
        price = "".join([str(p.get("text", "")) for p in price_parts if isinstance(p, dict)])
        price = price.replace("当前价", "").strip()
        if "万" in price:
            try:
                price = f"¥{float(price.replace('¥', '').replace('万', '')) * 10000:.0f}"
            except ValueError:
                pass

    area = safe_get(main_data, "area", default="地区未知")
    seller = safe_get(main_data, "userNickName", default="匿名卖家")
    raw_link = safe_get(item, "data", "item", "main", "targetUrl", default="")
    image_url = safe_get(main_data, "picUrl", default="")
    publish_raw = str(click_params.get("publishTime", "") or "")

    return {
        "商品标题": title,
        "当前售价": price,
        "发货地区": area,
        "卖家昵称": seller,
        "商品链接": str(raw_link).replace("fleamarket://", "https://www.goofish.com/"),
        "商品图片链接": (
            f"https:{image_url}" if image_url and not str(image_url).startswith("http") else image_url
        ),
        "发布时间": (
            datetime.fromtimestamp(int(publish_raw) / 1000).strftime("%Y-%m-%d %H:%M")
            if publish_raw.isdigit()
            else "未知时间"
        ),
    }


DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite://xianyu.db"
DATABASE_CONFIG = {
    "connections": {
        "default": DATABASE_URL
    },
    "apps": {
        "models": {
            "models": ["models"],
            "default_connection": "default",
        }
    },
}

register_tortoise(
    app,
    config=DATABASE_CONFIG,
    generate_schemas=True,
    add_exception_handlers=True,
)


async def save_to_db(data_list: List[Dict[str, Any]]) -> Tuple[int, List[int]]:
    """逐条保存数据到数据库，按链接哈希去重。"""
    new_records = 0
    new_ids: List[int] = []
    for item in data_list:
        try:
            link = item["商品链接"]
            unique_part = get_link_unique_key(link)
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
                    "publish_time": (
                        datetime.strptime(item["发布时间"], "%Y-%m-%d %H:%M")
                        if item["发布时间"] != "未知时间"
                        else None
                    ),
                },
            )
            if created:
                new_records += 1
                new_ids.append(product.id)
        except Exception as e:
            print(f"保存数据出错: {str(e)}")
    return new_records, new_ids


async def dismiss_blocking_modals(page: Page, timeout_ms: int = 2000) -> None:
    """关闭登录框/广告等遮罩，避免后续点击被拦截。"""
    locators = [
        page.locator("div[class*='closeIconBg']"),
        page.locator("button.ant-modal-close"),
        page.locator(".ant-modal-close"),
    ]
    for loc in locators:
        try:
            if await loc.count() == 0:
                continue
            target = loc.first
            if await target.is_visible():
                await target.click(timeout=timeout_ms)
                await page.wait_for_timeout(300)
        except Exception:
            continue


async def wait_for_new_items(data_list: List[Dict[str, Any]], previous_len: int, timeout_s: float = 8.0) -> None:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        if len(data_list) > previous_len:
            await asyncio.sleep(0.4)
            return
        await asyncio.sleep(0.15)


async def scrape_xianyu(keyword: str, max_pages: int = 1) -> List[Dict[str, Any]]:
    """异步爬取闲鱼商品数据。"""
    data_list: List[Dict[str, Any]] = []
    seen_keys = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=DEFAULT_UA,
            locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        async def on_response(response) -> None:
            if SEARCH_API_MARK not in response.url:
                return
            try:
                result_json = await response.json()
            except Exception:
                return
            items = (result_json.get("data") or {}).get("resultList") or []
            if result_json.get("ret") and "SUCCESS" not in str(result_json.get("ret")):
                print(f"搜索接口返回异常: {result_json.get('ret')}")
            for item in items:
                parsed = parse_product_item(item)
                if not parsed:
                    continue
                unique_key = get_link_unique_key(parsed["商品链接"])
                if unique_key in seen_keys:
                    continue
                seen_keys.add(unique_key)
                data_list.append(parsed)

        page.on("response", on_response)

        try:
            await page.goto("https://www.goofish.com", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1500)
            await dismiss_blocking_modals(page)

            search_input = page.locator('input[class*="search-input"]')
            await search_input.first.wait_for(state="visible", timeout=15000)
            await search_input.first.fill(keyword)
            try:
                await page.locator('button[type="submit"]').first.click(timeout=5000)
            except Exception:
                await search_input.first.press("Enter")

            await wait_for_new_items(data_list, 0, timeout_s=10)
            await dismiss_blocking_modals(page)

            try:
                await page.get_by_text("新发布", exact=True).first.click(timeout=4000)
                await page.wait_for_timeout(400)
                await page.get_by_text("最新", exact=True).first.click(timeout=4000)
                await wait_for_new_items(data_list, len(data_list), timeout_s=6)
            except Exception as e:
                print(f"排序点击跳过（不影响默认搜索结果）: {e}")

            current_page = 1
            while current_page < max_pages:
                print(f"正在处理第 {current_page} 页，准备翻页")
                await dismiss_blocking_modals(page)
                next_btn = page.locator("[class*='search-pagination-arrow-right']").first
                if await next_btn.count() == 0:
                    break
                class_name = (await next_btn.get_attribute("class")) or ""
                disabled = await next_btn.get_attribute("disabled")
                if disabled is not None or "disabled" in class_name:
                    break
                previous_len = len(data_list)
                try:
                    await next_btn.click(timeout=5000)
                except Exception as e:
                    print(f"翻页失败: {e}")
                    break
                await wait_for_new_items(data_list, previous_len, timeout_s=8)
                current_page += 1
        finally:
            await browser.close()

    return data_list


@app.get("/health", summary="健康检查")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/search/",
    summary="商品搜索接口",
    description="接收搜索关键词和页数，返回爬取结果数量、新增记录数量及新增记录的id列表",
)
async def search_items(payload: SearchRequest):
    try:
        data_list = await scrape_xianyu(payload.keyword, payload.max_pages)
        new_count, new_ids = (0, [])
        if data_list:
            new_count, new_ids = await save_to_db(data_list)
        return {
            "status": "success",
            "keyword": payload.keyword,
            "total_results": len(data_list),
            "new_records": new_count,
            "new_record_ids": new_ids,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"爬取失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
