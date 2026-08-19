import json
import random
import string
import time
import uuid
from typing import Optional, Any, Literal, Callable
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel
from pydantic.main import IncEx

from im_protocol import (
    cookie_user_id,
    dump_cookie_header,
    parse_cookie_header,
)
from session_store import load_session, save_session, clear_session

BASE_URL = "https://h5api.m.goofish.com/h5/{}/1.0/"
APPKEY = "34839810"
PASSPORT_BASE = "https://passport.goofish.com"
IM_APP_KEY = "444e9908a51d1cb236a27862abc769c9"
LOGIN_USER_API = "mtop.taobao.idlemessage.pc.loginuser.get"
IM_TOKEN_API = "mtop.taobao.idlemessage.pc.login.token"

client = httpx.AsyncClient(timeout=20.0)
SEARCH_API = "mtop.taobao.idlemtopsearch.pc.search"

_qr_sessions: dict[str, dict] = {}
_device_id: Optional[str] = None
_user_info: dict = {}


def _dump_data(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"))


def _h5_token() -> str:
    raw = client.cookies.get("_m_h5_tk")
    if not raw:
        raise RuntimeError("缺少 _m_h5_tk，无法签名搜索请求")
    return raw.split("_")[0]


class QueryParams(BaseModel):
    jsv: str = "2.7.2"
    appKey: str = APPKEY
    t: int
    sign: str
    v: str = "1.0"
    type: str = "originaljson"
    accountSite: str = "xianyu"
    dataType: str = "json"
    timeout: int = 20000
    api: str
    sessionOption: str = "AutoLoginOnly"
    spm_cnt: str
    spm_pre: Optional[str] = None

    @classmethod
    def create(cls, token: Optional[str], data: dict, api: str, spm_cnt: str, spm_pre: Optional[str] = None):
        if not token:
            token = "undefined"
        t = int(time.time() * 1000)
        sign = generate_sign(token, APPKEY, data, t)
        return cls(t=t, api=api, spm_cnt=spm_cnt, spm_pre=spm_pre, sign=sign)

    def model_dump(
            self,
            *,
            mode: Literal['json', 'python'] | str = 'python',
            include: IncEx | None = None,
            exclude: IncEx | None = None,
            context: Any | None = None,
            by_alias: bool | None = None,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = True,
            round_trip: bool = False,
            warnings: bool | Literal['none', 'warn', 'error'] = True,
            fallback: Callable[[Any], Any] | None = None,
            serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        return super().model_dump(mode=mode, include=include, exclude=exclude, context=context,
                                  by_alias=by_alias, exclude_unset=exclude_unset,
                                  exclude_defaults=exclude_defaults, exclude_none=True & exclude_none,
                                  round_trip=round_trip, warnings=warnings, fallback=fallback,
                                  serialize_as_any=serialize_as_any)


async def init():
    client.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"})
    # A cookie used to trace user behavior, thus can be randomly generated
    client.cookies.update({
        'cna': "".join(random.choices(string.ascii_letters + string.digits, k=25)),
    })
    await client.get("https://www.goofish.com/")
    await init_h5tk()
    if not client.cookies.get("_m_h5_tk"):
        raise RuntimeError("初始化闲鱼 token 失败")
    saved = load_session()
    if saved and saved.get("cookies"):
        apply_cookies(saved["cookies"])
        global _device_id, _user_info
        _device_id = saved.get("device_id") or _device_id
        _user_info = saved.get("user") or {}
        await init_h5tk()


async def init_h5tk():
    """
    Initialize the _m_h5_tk cookie by making a request to the announcement page.
    The _m_h5_tk cookie is required for authenticated API requests.
    """
    data = {"piUrl": "https://h5.m.goofish.com/wow/moyu/moyu-project/xy-site/pages/announcement"}
    qp = QueryParams.create(token=None, data=data, api="mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get",
                            spm_cnt="a21ybx.home.0.0")
    response = await client.post(
        BASE_URL.format("mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get"),
        params=qp.model_dump(),
        data={"data": _dump_data(data)},
    )
    response.raise_for_status()


def generate_sign(token: str, appkey: str, data: dict, j: int):
    """
    Generate the sign parameter for the API request.

    sign = md5(d.token + "&" + j + "&" + h + "&" + c.data)
    j = (new Date).getTime()
    h = appkey
    """
    import hashlib
    data = json.dumps(data, separators=(',', ':'))
    h = appkey
    sign_str = f"{token}&{j}&{h}&{data}"
    sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    return sign


def current_cookies() -> dict[str, str]:
    return {cookie.name: cookie.value for cookie in client.cookies.jar}


def apply_cookies(cookie: str | dict[str, str]) -> None:
    pairs = cookie if isinstance(cookie, dict) else parse_cookie_header(cookie)
    for name, value in pairs.items():
        client.cookies.set(name, value)


def persist_login(user: Optional[dict] = None) -> dict:
    global _device_id, _user_info
    cookies = current_cookies()
    user_id = cookie_user_id(cookies)
    if user:
        _user_info = user
    if not _device_id:
        _device_id = f"{uuid.uuid4()}-{user_id or '0'}"
    payload = {
        "cookies": dump_cookie_header(cookies),
        "device_id": _device_id,
        "user": _user_info,
        "user_id": user_id,
    }
    save_session(payload)
    return payload


def login_snapshot() -> dict:
    cookies = current_cookies()
    user_id = cookie_user_id(cookies)
    return {
        "logged_in": bool(user_id or _user_info),
        "user_id": user_id or _user_info.get("userId") or _user_info.get("user_id") or "",
        "user": _user_info,
        "device_id": _device_id,
        "has_h5_token": bool(client.cookies.get("_m_h5_tk")),
    }


def _mtop_ok(result: dict) -> bool:
    ret = result.get("ret") or []
    return any(str(item).startswith("SUCCESS") for item in ret)


async def mtop_request(
    api: str,
    data: Optional[dict] = None,
    *,
    spm_cnt: str = "a21ybx.im.0.0",
    spm_pre: Optional[str] = None,
    retry_token: bool = True,
) -> dict:
    payload = data or {}
    data_final = _dump_data(payload)
    qp = QueryParams.create(
        token=_h5_token(),
        data=payload,
        api=api,
        spm_cnt=spm_cnt,
        spm_pre=spm_pre,
    )
    response = await client.post(
        BASE_URL.format(api),
        params=qp.model_dump(),
        data={"data": data_final},
    )
    response.raise_for_status()
    result = response.json()
    ret = result.get("ret") or []
    token_expired = any("TOKEN" in str(item).upper() and "EXPIRED" in str(item).upper() for item in ret)
    fail_sys = any("FAIL_SYS" in str(item) for item in ret)
    if retry_token and (token_expired or (fail_sys and "SESSION" not in str(ret).upper())):
        await init_h5tk()
        qp = QueryParams.create(
            token=_h5_token(),
            data=payload,
            api=api,
            spm_cnt=spm_cnt,
            spm_pre=spm_pre,
        )
        response = await client.post(
            BASE_URL.format(api),
            params=qp.model_dump(),
            data={"data": data_final},
        )
        response.raise_for_status()
        result = response.json()
    return result


async def fetch_login_user() -> dict:
    result = await mtop_request(LOGIN_USER_API, {}, spm_cnt="a21ybx.im.0.0")
    if not _mtop_ok(result):
        raise RuntimeError(f"未登录或登录已失效: {result.get('ret')}")
    global _user_info
    _user_info = result.get("data") or {}
    persist_login(_user_info)
    return _user_info


async def fetch_im_token(device_id: Optional[str] = None) -> dict:
    global _device_id
    cookies = current_cookies()
    user_id = cookie_user_id(cookies)
    _device_id = device_id or _device_id or f"{uuid.uuid4()}-{user_id or '0'}"
    result = await mtop_request(
        IM_TOKEN_API,
        {"appKey": IM_APP_KEY, "deviceId": _device_id},
        spm_cnt="a21ybx.im.0.0",
        spm_pre="a21ybx.im.0.0",
    )
    if not _mtop_ok(result):
        raise RuntimeError(f"获取 IM Token 失败: {result.get('ret')}")
    data = result.get("data") or {}
    persist_login()
    return {
        "access_token": data.get("accessToken") or data.get("access_token") or "",
        "raw": data,
        "device_id": _device_id,
        "user_id": user_id,
    }


async def login_with_cookie(cookie: str) -> dict:
    if not cookie or "=" not in cookie:
        raise ValueError("Cookie 不能为空")
    apply_cookies(cookie)
    await init_h5tk()
    user = await fetch_login_user()
    return login_snapshot() | {"user": user}


def logout() -> None:
    global _device_id, _user_info
    client.cookies.clear()
    _device_id = None
    _user_info = {}
    clear_session()
    _qr_sessions.clear()


def _passport_headers() -> dict[str, str]:
    return {
        "User-Agent": client.headers.get(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ),
        "Referer": f"{PASSPORT_BASE}/mini_login.htm",
        "Origin": PASSPORT_BASE,
    }


async def start_qr_login() -> dict:
    """通过 passport HTTP 接口生成登录二维码。"""
    await client.get(
        f"{PASSPORT_BASE}/mini_login.htm",
        params={
            "lang": "zh_cn",
            "appName": "xianyu",
            "appEntrance": "web",
            "styleType": "vertical",
            "notLoadSsoView": "false",
            "notKeepLogin": "false",
            "isMobile": "false",
            "qrCodeFirst": "true",
        },
        headers=_passport_headers(),
    )
    csrf = client.cookies.get("XSRF-TOKEN") or client.cookies.get("_csrf_token") or ""
    cookie2 = client.cookies.get("cookie2") or ""
    params = {
        "appName": "xianyu",
        "fromSite": "77",
        "appEntrance": "web",
        "_csrf_token": csrf,
        "umidToken": "",
        "hsiz": cookie2,
        "bizParams": "taobaoBizLoginFrom=web&renderRefer=https://www.goofish.com/",
        "mainPage": "false",
        "isMobile": "false",
        "lang": "zh_CN",
        "returnUrl": "",
        "umidTag": "SERVER",
    }
    response = await client.get(
        f"{PASSPORT_BASE}/newlogin/qrcode/generate.do",
        params=params,
        headers=_passport_headers(),
    )
    response.raise_for_status()
    body = response.json()
    data = ((body.get("content") or {}).get("data")) or body.get("data") or {}
    if not data.get("codeContent") and not data.get("t"):
        raise RuntimeError(f"二维码生成失败: {body}")
    session_id = uuid.uuid4().hex
    _qr_sessions[session_id] = {
        "t": data.get("t"),
        "ck": data.get("ck"),
        "csrf": csrf,
        "cookie2": cookie2,
        "status": "NEW",
        "code_content": data.get("codeContent") or "",
    }
    qr_image = ""
    try:
        import io
        import qrcode

        image = qrcode.make(_qr_sessions[session_id]["code_content"])
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        import base64

        qr_image = base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        qr_image = ""
    return {
        "session_id": session_id,
        "status": "NEW",
        "qr_content": _qr_sessions[session_id]["code_content"],
        "qr_image_base64": qr_image,
        "message": "请用闲鱼 App 扫描二维码，然后轮询 /auth/qr/status",
    }


async def poll_qr_login(session_id: str) -> dict:
    session = _qr_sessions.get(session_id)
    if not session:
        raise KeyError("二维码会话不存在或已过期，请重新生成")
    form = {
        "t": str(session.get("t") or ""),
        "ck": session.get("ck") or "",
        "appName": "xianyu",
        "fromSite": "77",
        "appEntrance": "web",
        "_csrf_token": session.get("csrf") or "",
        "umidToken": "",
        "hsiz": session.get("cookie2") or "",
        "bizParams": "taobaoBizLoginFrom=web&renderRefer=https://www.goofish.com/",
        "mainPage": "false",
        "isMobile": "false",
        "lang": "zh_CN",
        "returnUrl": "",
        "umidTag": "SERVER",
        "navlanguage": "zh-CN",
        "navUserAgent": client.headers.get("User-Agent", ""),
        "navPlatform": "Win32",
        "isIframe": "true",
        "documentReferer": "https://www.goofish.com/",
        "defaultView": "qrcode",
    }
    response = await client.post(
        f"{PASSPORT_BASE}/newlogin/qrcode/query.do",
        params={"appName": "xianyu", "fromSite": "77"},
        data=urlencode(form),
        headers={**_passport_headers(), "Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    body = response.json()
    data = ((body.get("content") or {}).get("data")) or body.get("data") or {}
    status = data.get("qrCodeStatus") or data.get("status") or "NEW"
    session["status"] = status
    result = {"session_id": session_id, "status": status, "logged_in": False}
    if status != "CONFIRMED":
        return result
    login_token = data.get("token") or data.get("lgToken")
    if login_token:
        await client.post(
            f"{PASSPORT_BASE}/login_token/login.do",
            params={
                "token": login_token,
                "subFlow": "DIALOG_CHECK_LOGIN_RPC",
                "nextCode": "0018",
                "bizScene": "qrcode",
                "confirm": "true",
            },
            data={"deviceId": client.cookies.get("cna") or ""},
            headers=_passport_headers(),
        )
    await init_h5tk()
    try:
        user = await fetch_login_user()
    except Exception as exc:
        persist_login()
        result["logged_in"] = bool(cookie_user_id(current_cookies()))
        result["warning"] = str(exc)
        result["user"] = login_snapshot()
        _qr_sessions.pop(session_id, None)
        return result
    _qr_sessions.pop(session_id, None)
    result["logged_in"] = True
    result["user"] = user
    return result


async def search(keyword: str, page: int = 1):
    # 对齐原版 Playwright 点击「新发布 / 最新」后的请求体
    data = {
        "pageNumber": page,
        "keyword": keyword,
        "fromFilter": True,
        "rowsPerPage": 30,
        "sortValue": "desc",
        "sortField": "create",
        "customDistance": "",
        "gps": "",
        "propValueStr": {"searchFilter": ""},
        "customGps": "",
        "searchReqFromPage": "pcSearch",
        "extraFilterValue": "{}",
        "userPositionJson": "{}",
    }
    data_final = _dump_data(data)
    url = BASE_URL.format(SEARCH_API)
    qp = QueryParams.create(
        token=_h5_token(),
        data=data,
        api=SEARCH_API,
        spm_cnt="a21ybx.search.0.0",
        spm_pre="a21ybx.search.searchInput.0",
    )
    response = await client.post(url, params=qp.model_dump(), data={"data": data_final})
    response.raise_for_status()
    result = response.json()
    ret = result.get("ret") or []
    if not any(str(item).startswith("SUCCESS") for item in ret):
        raise RuntimeError(f"搜索接口调用失败: {ret}")
    return result
