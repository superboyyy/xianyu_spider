import logging

from tortoise import Model, Tortoise, fields

logger = logging.getLogger(__name__)


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
    conversation_id = fields.CharField(max_length=128, db_index=True, description="会话 ID")
    sender_id = fields.CharField(max_length=64, default="", description="发送者 ID")
    sender_name = fields.CharField(max_length=128, default="", description="发送者昵称")
    text = fields.TextField(description="文本内容")
    direction = fields.CharField(max_length=8, default="in", description="in / out")
    source = fields.CharField(max_length=16, default="", description="user / gateway / rule / ai")
    raw_json = fields.TextField(null=True, description="原始推送")
    created_at = fields.DatetimeField(auto_now_add=True, description="入库时间")

    class Meta:
        table = "im_messages"


class Watch(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=120, default="")
    keyword = fields.CharField(max_length=200)
    sort = fields.CharField(max_length=32, default="newest")
    min_price = fields.IntField(null=True)
    max_price = fields.IntField(null=True)
    city = fields.CharField(max_length=64, null=True)
    province = fields.CharField(max_length=64, null=True)
    publish_days = fields.IntField(null=True)
    max_pages = fields.IntField(default=1)
    interval_minutes = fields.IntField(default=15)
    enabled = fields.BooleanField(default=True)
    notify_new = fields.BooleanField(default=True)
    notify_below_target = fields.BooleanField(default=True)
    target_price = fields.FloatField(null=True)
    notify_below_median_pct = fields.FloatField(null=True)
    last_run_at = fields.DatetimeField(null=True)
    last_error = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "watches"


class WatchRun(Model):
    id = fields.IntField(pk=True)
    watch: fields.ForeignKeyRelation[Watch] = fields.ForeignKeyField(
        "models.Watch", related_name="runs", on_delete=fields.CASCADE
    )
    status = fields.CharField(max_length=32, default="ok")
    total_results = fields.IntField(default=0)
    new_records = fields.IntField(default=0)
    min_price = fields.FloatField(null=True)
    triggered = fields.JSONField(default=list)
    error = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "watch_runs"


class PriceSnapshot(Model):
    id = fields.IntField(pk=True)
    keyword = fields.CharField(max_length=200, db_index=True, default="")
    product_id = fields.IntField(null=True, db_index=True)
    item_id = fields.CharField(max_length=64, default="", db_index=True)
    link_hash = fields.CharField(max_length=32, default="", db_index=True)
    title = fields.CharField(max_length=255, default="")
    price_text = fields.CharField(max_length=50, default="")
    price_value = fields.FloatField(null=True)
    city = fields.CharField(max_length=64, null=True)
    watch_id = fields.IntField(null=True, db_index=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "price_snapshots"


class NotifyChannel(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=80, default="Bark")
    kind = fields.CharField(max_length=32, default="bark")
    endpoint = fields.TextField(description="Bark key 或完整推送 URL / webhook URL")
    enabled = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "notify_channels"


class NotifyEvent(Model):
    id = fields.IntField(pk=True)
    channel_id = fields.IntField(null=True)
    event_type = fields.CharField(max_length=64)
    fingerprint = fields.CharField(max_length=64, db_index=True)
    title = fields.CharField(max_length=200, default="")
    body = fields.TextField(default="")
    payload = fields.JSONField(default=dict)
    ok = fields.BooleanField(default=False)
    error = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "notify_events"


class AiThread(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=200, default="新对话")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "ai_threads"


class AiMessage(Model):
    id = fields.IntField(pk=True)
    thread: fields.ForeignKeyRelation[AiThread] = fields.ForeignKeyField(
        "models.AiThread", related_name="messages", on_delete=fields.CASCADE
    )
    role = fields.CharField(max_length=16)
    content = fields.TextField(default="")
    refs = fields.JSONField(default=list)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "ai_messages"


class AutoreplyRule(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=80, default="")
    enabled = fields.BooleanField(default=True)
    match_text = fields.CharField(max_length=200, default="")
    reply_text = fields.TextField(default="")
    cooldown_seconds = fields.IntField(default=300)
    only_first = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "autoreply_rules"


class AutoreplyLog(Model):
    id = fields.IntField(pk=True)
    conversation_id = fields.CharField(max_length=128, db_index=True)
    rule_id = fields.IntField(null=True)
    mode = fields.CharField(max_length=16, default="draft")
    incoming = fields.TextField(default="")
    reply = fields.TextField(default="")
    status = fields.CharField(max_length=32, default="draft")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "autoreply_logs"


async def ensure_im_schema() -> list[str]:
    """旧表用 content/replied，新模型用 text/source。generate_schemas 不会改已有表。"""
    conn = Tortoise.get_connection("default")
    try:
        _, rows = await conn.execute_query("PRAGMA table_info(im_messages)")
    except Exception:
        return []
    names = {row[1] for row in rows}
    if not names:
        return []
    if "text" in names and "source" in names and "content" not in names:
        return []
    text_expr = "text" if "text" in names else "content" if "content" in names else "''"
    source_expr = "source" if "source" in names else "''"
    await conn.execute_script(
        f"""
        CREATE TABLE im_messages_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            conversation_id VARCHAR(128) NOT NULL,
            sender_id VARCHAR(64) NOT NULL DEFAULT '',
            sender_name VARCHAR(128) NOT NULL DEFAULT '',
            text TEXT NOT NULL,
            direction VARCHAR(8) NOT NULL DEFAULT 'in',
            source VARCHAR(16) NOT NULL DEFAULT '',
            raw_json TEXT,
            created_at TIMESTAMP NOT NULL
        );
        INSERT INTO im_messages_new
            (id, conversation_id, sender_id, sender_name, text, direction, source, raw_json, created_at)
        SELECT
            id, conversation_id, sender_id, sender_name, {text_expr}, direction, {source_expr}, raw_json, created_at
        FROM im_messages;
        DROP TABLE im_messages;
        ALTER TABLE im_messages_new RENAME TO im_messages;
        CREATE INDEX IF NOT EXISTS idx_im_messages_conversation_id ON im_messages (conversation_id);
        """
    )
    logger.info("im_messages 已从旧结构迁移到 text/source")
    return ["rebuild im_messages"]
