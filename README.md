# 闲鱼 HTTP 接口

[![FastAPI](https://img.shields.io/badge/FastAPI-0.68.0-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)

基于 FastAPI + httpx 的闲鱼网页接口封装：商品搜索走 mtop HTTP；登录走 Cookie / 扫码 HTTP；私信收发沿用官网同款 IM WebSocket，再由本服务转成 HTTP / SSE / Webhook。

## 能通过请求实现吗？

| 能力 | 对本服务 | 对闲鱼侧 |
|------|----------|----------|
| 登录 | `POST /auth/cookie` 导入网页 Cookie；本机桌面也可用 `python spider.py login` | 账号密码基本不可用（滑块）。纯 HTTP 扫码常被拍脸拦住；能跑通的是官方登录页扫码或 Cookie 导入 |
| 自动回复 | `PUT /im/config` + `POST /im/start` | 取 Token 是 HTTP，真正收发消息必须维持 `wss://wss-goofish.dingtalk.com/` 长连接 |
| 收到消息通知 | `GET /im/events`（SSE）或配置 `webhook_url` | 同上，闲鱼不会用普通 REST 推私信 |

结论：**业务接口可以全部用本仓库的 HTTP API 来驱动**。登录请用 Cookie 导入，或本机有桌面时用 Playwright 打开官方登录页扫码。底层私信通道和网页版一样是 WebSocket，不能改成一次性 REST 轮询。

## 功能特性

- 关键词商品搜索（HTTP 直连，按最新发布排序）
- Cookie 导入登录、扫码登录、登录态检查
- 关键词 / 默认文案自动回复
- 收到消息后 Webhook 回调 + SSE 实时通知
- 商品结果按链接哈希去重入库

## 快速开始

```bash
pip install -r requirements.txt
```

`.env` 可选。不配 `DATABASE_URL` 时默认使用 `data/xianyu.sqlite3`。

```env
DATABASE_URL=mysql://user:password@localhost/xianyu
```

```bash
python spider.py
```

打开 `http://localhost:8000/docs`。

登录（社区能跑通的两条路）：

```bash
# 1) 推荐：打开闲鱼官方登录页，用 App 扫弹出窗口里的码；拍脸也在同一窗口完成
pip install playwright && playwright install chromium
python spider.py login

# 2) 最稳：先在系统浏览器登录 https://www.goofish.com ，F12 复制 Cookie
python spider.py login --cookie
```

## 测试

```bash
pip install pytest
pytest
```

当前覆盖：Cookie/签名/自动回复匹配的单元测试，以及不连闲鱼账号的 FastAPI 接口测试。

真实搜索（会请求闲鱼）：

```bash
RUN_LIVE=1 pytest tests/test_live_search.py
```

登录、自动回复、IM 收消息需要你自己的 Cookie/扫码，仓库里没有账号，所以没有做成默认 CI。

## 目录结构

```
spider.py                 # 启动入口：python spider.py / python spider.py login
xianyu/
  app.py                  # FastAPI 组装
  cli.py                  # 登录：默认官方登录页扫码 / --cookie / --http 画码
  mtop.py                 # 闲鱼 mtop HTTP（搜索/登录/IM Token）
  protocol.py             # Cookie 与 IM 推送解析、自动回复匹配
  im_client.py            # IM WebSocket
  im_worker.py            # 监听、自动回复、Webhook/SSE
  models.py / schemas.py  # 数据库与请求体
  routers/                # /search /auth /im
tests/                    # pytest
test.py                   # 旧的 Playwright 手工脚本，搜索主路径已不用它
```

## 登录

闲鱼账号密码基本打不开（滑块）。GitHub 上能跑通的项目（[goofish-cli](https://github.com/fancyboi999/goofish-cli)、[XianyuAutoAgent](https://github.com/shaxiu/XianyuAutoAgent)）都是下面两条路，本仓库已经对齐：

### 1. 官方登录页扫码（默认）

本机要有桌面。会弹出真实浏览器，打开 `https://www.goofish.com/login`，用闲鱼 App 扫**窗口里**的码；若要拍脸，也在这个窗口完成。程序轮询 Cookie，直到 `_m_h5_tk`、`unb`、`cookie2` 齐全再写入 `data/session.json`。

```bash
pip install playwright && playwright install chromium
python spider.py login
```

不要去粘贴拍脸后的 `ivCheckLogin.htm` 白屏链接，那个页面本身不会种登录 Cookie。

### 2. 粘贴网页 Cookie（最稳，无桌面也能用）

1. 用系统 Chrome / Edge 打开 https://www.goofish.com 并登录（含拍脸）。
2. F12 → Application/存储 → Cookies → 复制 `www.goofish.com` 的 Cookie（至少要有 `unb`，以及 `cookie2` 或 `_m_h5_tk`）。

```bash
python spider.py login --cookie
# 或
curl -X POST http://localhost:8000/auth/cookie \
  -H 'Content-Type: application/json' \
  -d '{"cookie":"unb=xxxx; cookie2=xxxx; _m_h5_tk=xxxx; ..."}'
```

`GET /auth/status` 可检查是否仍登录。

### 不要用

- `python spider.py login --http`：终端画码纯 HTTP，确认登录后一旦要拍脸就换不了票。
- 把 `ivCheckLogin.htm?havana_iv_token=...` 白屏 URL 交给服务端 GET / POST，换不来登录态。

## 自动回复与通知

```bash
curl -X PUT http://localhost:8000/im/config \
  -H 'Content-Type: application/json' \
  -d '{
    "enabled": true,
    "default_reply": "您好{sender_name}，看到后会尽快回复。",
    "keyword_replies": [{"keyword": "在吗", "reply": "在的"}],
    "webhook_url": "https://example.com/xianyu-hook"
  }'

curl -X POST http://localhost:8000/im/start
```

- Webhook 在收到买家消息时 POST JSON：`event=message.received`，自动回复成功后再发 `message.replied`
- `GET /im/events` 为 SSE 长连接，适合自己的前端/机器人订阅
- `GET /im/messages` 查看最近入库的消息

占位符：`{sender_name}` `{text}` `{conversation_id}` `{sender_id}`

## 搜索接口

```
POST /search/?keyword=手机&max_pages=1
```

## 注意事项

1. 仅用于自己的账号客服/学习研究，请遵守闲鱼用户协议与《网络安全法》。
2. Cookie 与 IM Token 会过期，掉线后重新登录并 `POST /im/start`。
3. 闲鱼 IM 推送格式可能变化；文本消息一般可解析，部分卡片/加密包可能只有通知没有正文。
4. 不要把 `data/session.json` 提交到 Git。

本项目采用 [MIT License](LICENSE)。
