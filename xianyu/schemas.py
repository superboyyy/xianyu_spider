from typing import Optional

from pydantic import BaseModel, Field, field_validator

from xianyu.search_query import SORT_OPTIONS


class CookieLoginBody(BaseModel):
    cookie: str = Field(..., description="浏览器登录闲鱼后复制的完整 Cookie")


class SendMessageBody(BaseModel):
    conversation_id: str = Field(..., description="会话 ID，可带或不带 @goofish")
    to_user_id: str = Field(..., description="对方闲鱼 user id")
    text: str = Field(..., min_length=1, description="文本")
    source: str = Field("user", description="user 或 agent，仅作记录")


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
