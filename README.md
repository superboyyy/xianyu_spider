# 闲鱼 HTTP 接口

[![FastAPI](https://img.shields.io/badge/FastAPI-0.68.0-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)

基于 FastAPI + httpx 的闲鱼网页接口封装：商品搜索走 mtop HTTP；登录走 Cookie / 扫码 HTTP；私信收发沿用官网同款 IM WebSocket，再由本服务转成 HTTP / SSE / Webhook。

## 能通过请求实现吗？

| 能力 | 对本服务 | 对闲鱼侧 |
|------|----------|----------|
| 登录 | `POST /auth/cookie` 或扫码 HTTP 接口 | Passport / mtop HTTP。账号密码基本不可用（滑块风控），请用 Cookie 或 App 扫码 |
| 自动回复 | `PUT /im/config` + `POST /im/start` | 取 Token 是 HTTP，真正收发消息必须维持 `wss://wss-goofish.dingtalk.com/` 长连接 |
| 收到消息通知 | `GET /im/events`（SSE）或配置 `webhook_url` | 同上，闲鱼不会用普通 REST 推私信 |

结论：**可以全部用本仓库的 HTTP API 来驱动**，不需要 Playwright。底层私信通道和网页版一样是 WebSocket，不能改成一次性 REST 轮询。

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

终端扫码登录（直接在命令行画出二维码）：

```bash
python spider.py login
```

用闲鱼 App 扫终端里的码并点确认。若还要二次验证，终端会再画出验证二维码，请用 App 内「扫一扫」。

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
  cli.py                  # 终端扫码登录（ASCII 二维码）
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

浏览器登录 [闲鱼网页版](https://www.goofish.com) 后，从开发者工具复制 Cookie：

```bash
curl -X POST http://localhost:8000/auth/cookie \
  -H 'Content-Type: application/json' \
  -d '{"cookie":"unb=xxxx; cookie2=xxxx; _m_h5_tk=xxxx; ..."}'
```

或在终端扫码（推荐）：

```bash
python spider.py login
```

也可以自己调接口。`POST /auth/qr/start` 会返回 `qr_ascii`，可直接在终端打印：

```bash
curl -s -X POST http://localhost:8000/auth/qr/start | python -c 'import sys,json; print(json.load(sys.stdin)["qr_ascii"])'
curl 'http://localhost:8000/auth/qr/status?session_id=返回的session_id'
# 或：curl 'http://localhost:8000/auth/qr/text?session_id=返回的session_id'
```

`GET /auth/status` 可检查是否仍登录。登录态会写入 `data/session.json`。

### 扫码后仍显示未登录？

1. 扫码后必须在闲鱼 App 点「确认登录」。接口里的 `SCANED` / `scanned` 只表示已扫码，还不是已登录。
2. 请轮询 `GET /auth/qr/status?session_id=...` 直到 `logged_in: true`。只刷新 `GET /auth/status` 看不到扫码进度。
3. 若返回 `verification_required` 且 `face_verify: true`：这是官方「拍摄脸部」核身页，**不要扫验证页链接生成的码**（手机会套娃）。`python spider.py login` 会打印链接并用系统默认浏览器打开；用闲鱼 App 扫浏览器里的码并拍脸，拍完不要关页面，终端会继续换登录态。不必用 Playwright。不要重新 `POST /auth/qr/start`。
4. 默认浏览器跳转后仍未登录时，再把网页 Cookie 贴到 `POST /auth/cookie`，或用 continue 页的 Playwright 后备导入。

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
