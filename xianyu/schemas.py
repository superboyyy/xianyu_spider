from typing import Optional

from pydantic import BaseModel, Field


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
