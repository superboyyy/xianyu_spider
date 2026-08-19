from tortoise import Model, fields


class XianyuProduct(Model):
    id = fields.IntField(pk=True)
    title = fields.TextField(description="商品标题")
    price = fields.CharField(max_length=50, description="当前售价")
    area = fields.CharField(max_length=100, description="发货地区")
    seller = fields.CharField(max_length=100, description="卖家昵称")
    link = fields.TextField(description="商品链接")
    link_hash = fields.CharField(max_length=32, unique=True, description="商品链接哈希")
    image_url = fields.TextField(description="商品图片链接")
    publish_time = fields.DatetimeField(null=True, description="发布时间")

    class Meta:
        table = "xianyu_products"
