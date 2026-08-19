from spider import format_product_item, get_link_unique_key, get_md5, parse_product_item


def test_get_md5():
    assert get_md5("hello") == "5d41402abc4b2a76b9719d911017c592"


def test_get_link_unique_key_strips_query_tail():
    link = "https://www.goofish.com/item?id=123&foo=1&bar=2"
    assert get_link_unique_key(link) == "https://www.goofish.com/item?id=123"


def test_parse_product_item():
    item = {
        "data": {
            "item": {
                "main": {
                    "exContent": {
                        "title": "测试手机",
                        "price": [{"text": "当前价"}, {"text": "¥"}, {"text": "99"}],
                        "area": "上海",
                        "userNickName": "卖家A",
                        "picUrl": "//img.alicdn.com/test.jpg",
                    },
                    "clickParam": {"args": {"publishTime": "1710000000000"}},
                    "targetUrl": "fleamarket://item?id=1&x=2",
                }
            }
        }
    }
    parsed = parse_product_item(item)
    assert parsed["商品标题"] == "测试手机"
    assert parsed["当前售价"] == "¥99"
    assert parsed["发货地区"] == "上海"
    assert parsed["卖家昵称"] == "卖家A"
    assert parsed["商品链接"].startswith("https://www.goofish.com/")
    assert parsed["商品图片链接"].startswith("https:")
    assert parsed["发布时间"] != "未知时间"


def test_format_product_item():
    parsed = {
        "商品标题": "测试手机",
        "当前售价": "¥99",
        "发货地区": "上海",
        "卖家昵称": "卖家A",
        "商品链接": "https://www.goofish.com/item?id=1",
        "商品图片链接": "https://img.alicdn.com/test.jpg",
        "发布时间": "2026-01-01 12:00",
    }
    item = format_product_item(parsed, product_id=12, is_new=True)
    assert item["id"] == 12
    assert item["title"] == "测试手机"
    assert item["price"] == "¥99"
    assert item["area"] == "上海"
    assert item["seller"] == "卖家A"
    assert item["link"] == "https://www.goofish.com/item?id=1"
    assert item["image_url"] == "https://img.alicdn.com/test.jpg"
    assert item["publish_time"] == "2026-01-01 12:00"
    assert item["is_new"] is True


def test_format_product_item_unknown_time_is_null():
    item = format_product_item({"发布时间": "未知时间"}, product_id=None, is_new=False)
    assert item["publish_time"] is None
    assert item["id"] is None
    assert item["is_new"] is False
