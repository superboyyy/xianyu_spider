from xianyu.catalog import item_id_from_link, public_from_raw


def test_item_id_from_goofish_link():
    assert item_id_from_link("https://www.goofish.com/item?id=12345&foo=1") == "12345"
    assert item_id_from_link("fleamarket://item?id=99") == "99"
    assert item_id_from_link("") == ""


def test_public_from_raw_maps_chinese_keys():
    item = public_from_raw(
        {
            "商品标题": "旧相机",
            "当前售价": "¥800",
            "发货地区": "深圳",
            "卖家昵称": "店主",
            "商品链接": "https://www.goofish.com/item?id=99",
            "商品图片链接": "https://img.example/a.jpg",
            "发布时间": "2026-01-01 12:00",
            "seller_id": "88",
        },
        product_id=7,
        is_new=True,
    )
    assert item["id"] == 7
    assert item["item_id"] == "99"
    assert item["title"] == "旧相机"
    assert item["price"] == "¥800"
    assert item["seller_id"] == "88"
    assert item["is_new"] is True
    assert item["publish_time"] == "2026-01-01 12:00"
