from typing import Optional

from pydantic import BaseModel, Field


class CookieLoginBody(BaseModel):
    cookie: str = Field(..., description="浏览器登录闲鱼后复制的完整 Cookie")


class QrCallbackBody(BaseModel):
    session_id: str = Field(..., description="start 接口返回的 session_id")
    url: str = Field(..., description="浏览器地址栏的 ivCheckLogin.htm 完整链接")


class KeywordReply(BaseModel):
    keyword: str
    reply: str


class AutoReplyBody(BaseModel):
    enabled: Optional[bool] = None
    default_reply: Optional[str] = None
    keyword_replies: Optional[list[KeywordReply]] = None
    webhook_url: Optional[str] = None
