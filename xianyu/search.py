import asyncio
import hashlib
from datetime import datetime

from xianyu.models import XianyuProduct
from xianyu.mtop import search as mtop_search


def get_md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def get_link_unique_key(link: str) -> str:
    parts = link.split("&", 1)
    return parts[0] if len(parts) >= 2 else link


async def safe_get(data, *keys, default="暂无"):
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError, IndexError):
            return default
    return data


async def save_to_db(data_list):
    new_records = 0
    new_ids = []
    for item in data_list:
        try:
            link = item["商品链接"]
            link_hash = get_md5(get_link_unique_key(link))
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
                    if item["发布时间"] != "未知时间"
                    else None,
                },
            )
            if created:
                new_records += 1
                new_ids.append(product.id)
        except Exception as exc:
            print(f"保存数据出错: {exc}")
    return new_records, new_ids


async def handle_data(data: dict):
    if "NoneOfResult" in str(data):
        return []
    items = data.get("data", {}).get("resultList") or []
    res = []
    for item in items:
        main_data = await safe_get(item, "data", "item", "main", "exContent", default={})
        click_params = await safe_get(item, "data", "item", "main", "clickParam", "args", default={})
        title = await safe_get(main_data, "title", default="未知标题")
        price_parts = await safe_get(main_data, "price", default=[])
        price = "价格异常"
        if isinstance(price_parts, list):
            price = "".join([str(p.get("text", "")) for p in price_parts if isinstance(p, dict)])
            price = price.replace("当前价", "").strip()
            if "万" in price:
                price = f"¥{float(price.replace('¥', '').replace('万', '')) * 10000:.0f}"
        area = await safe_get(main_data, "area", default="地区未知")
        seller = await safe_get(main_data, "userNickName", default="匿名卖家")
        raw_link = await safe_get(item, "data", "item", "main", "targetUrl", default="")
        image_url = await safe_get(main_data, "picUrl", default="")
        publish_time = click_params.get("publishTime", "")
        res.append(
            {
                "商品标题": title,
                "当前售价": price,
                "发货地区": area,
                "卖家昵称": seller,
                "商品链接": raw_link.replace("fleamarket://", "https://www.goofish.com/"),
                "商品图片链接": f"https:{image_url}"
                if image_url and not image_url.startswith("http")
                else image_url,
                "发布时间": datetime.fromtimestamp(int(publish_time) / 1000).strftime("%Y-%m-%d %H:%M")
                if str(publish_time).isdigit()
                else "未知时间",
            }
        )
    return res


async def scrape_xianyu_http(keyword: str, max_pages: int = 1):
    semaphore = asyncio.Semaphore(3)

    async def fetch_page(page: int):
        async with semaphore:
            return page, await handle_data(await mtop_search(keyword, page))

    gathered = await asyncio.gather(*[fetch_page(page) for page in range(1, max_pages + 1)])
    res = []
    for _, items in sorted(gathered, key=lambda item: item[0]):
        res.extend(items)
    return res
