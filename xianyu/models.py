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
