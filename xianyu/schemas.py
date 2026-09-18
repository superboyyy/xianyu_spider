from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from xianyu.search_query import SORT_OPTIONS


class CookieLoginBody(BaseModel):
    cookie: str = Field(..., description="浏览器登录闲鱼后复制的完整 Cookie")


class SendMessageBody(BaseModel):
    conversation_id: str = Field(..., description="会话 ID，可带或不带 @goofish")
    to_user_id: str = Field(..., description="对方闲鱼 user id")
    text: str = Field(..., min_length=1, description="文本")
    source: str = Field("user", description="user / agent / rule / ai")


class QrCallbackBody(BaseModel):
    session_id: str = Field(..., description="start 接口返回的 session_id")
    url: str = Field(..., description="浏览器地址栏的 ivCheckLogin.htm 完整链接")


class SearchBody(BaseModel):
    keyword: str = Field(..., description="搜索关键词")
    max_pages: int = Field(1, ge=1, le=20, description="抓取页数")
    sort: str = Field("newest", description="newest / price_asc / price_desc / default")
    min_price: Optional[int] = Field(None, ge=0, description="最低价格（元）")
    max_price: Optional[int] = Field(None, ge=0, description="最高价格（元）")
    province: Optional[str] = Field(None, description="省份，如 广东")
    city: Optional[str] = Field(None, description="城市，如 深圳")
    publish_days: Optional[int] = Field(None, ge=1, le=180, description="最近几天发布")

    @field_validator("sort")
    @classmethod
    def validate_sort(cls, value: str) -> str:
        key = (value or "newest").strip().lower()
        if key not in SORT_OPTIONS:
            raise ValueError(f"不支持的排序: {value}，可选 {', '.join(SORT_OPTIONS)}")
        return key

    def filters(self):
        from xianyu.search_query import SearchFilters

        return SearchFilters(
            sort=self.sort,
            min_price=self.min_price,
            max_price=self.max_price,
            province=self.province,
            city=self.city,
            publish_days=self.publish_days,
        )


class WatchBody(BaseModel):
    name: str = ""
    keyword: str = Field(..., min_length=1)
    sort: str = "newest"
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    city: Optional[str] = None
    province: Optional[str] = None
    publish_days: Optional[int] = None
    max_pages: int = Field(1, ge=1, le=10)
    interval_minutes: int = Field(15, ge=1, le=24 * 60)
    enabled: bool = True
    notify_new: bool = True
    notify_below_target: bool = True
    target_price: Optional[float] = None
    notify_below_median_pct: Optional[float] = Field(None, ge=0, le=90)


class NotifyChannelBody(BaseModel):
    name: str = "Bark"
    kind: str = Field("bark", description="bark / webhook")
    endpoint: str = Field(..., min_length=1)
    enabled: bool = True


class NotifyTestBody(BaseModel):
    title: str = "闲鱼工作台"
    body: str = "测试推送"


class SettingsBody(BaseModel):
    autoreply_mode: Optional[str] = None
    ai_base_url: Optional[str] = None
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None


class AiChatBody(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: Optional[int] = None


class AutoreplyRuleBody(BaseModel):
    name: str = ""
    enabled: bool = True
    match_text: str = Field(..., min_length=1)
    reply_text: str = Field(..., min_length=1)
    cooldown_seconds: int = Field(300, ge=0)
    only_first: bool = False


def watch_to_dict(row: Any) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "keyword": row.keyword,
        "sort": row.sort,
        "min_price": row.min_price,
        "max_price": row.max_price,
        "city": row.city,
        "province": row.province,
        "publish_days": row.publish_days,
        "max_pages": row.max_pages,
        "interval_minutes": row.interval_minutes,
        "enabled": row.enabled,
        "notify_new": row.notify_new,
        "notify_below_target": row.notify_below_target,
        "target_price": row.target_price,
        "notify_below_median_pct": row.notify_below_median_pct,
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
