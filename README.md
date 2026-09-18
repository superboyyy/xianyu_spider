# 闲鱼工作台

本机闲鱼引擎 + 液态玻璃 Web 客户端（Vue 3）。支持搜货、货架、盯盘推送、多厂商 AI 问询、私信与草稿自动回复。

## 快速开始

```bash
pip install -r requirements.txt
playwright install chromium   # 扫脸认证需要

# 前端已构建在 web/；若改了 frontend/ 源码：
# cd frontend && npm install && npm run build && cp -a dist/. ../web/

python spider.py
```

打开 http://127.0.0.1:8000

| 页面 | 作用 |
|---|---|
| 搜货 | 关键词 / 价格 / 城市 |
| 货架 | 本机落库商品与均价样本 |
| 盯盘 | 定时搜索；上新 / 目标价 / 低于中位 |
| AI | 找货、均价、入手判断、起草私信 |
| 私信 | 闲鱼 IM（勿与网页版同时开） |
| 自动回复 | 规则命中后只出草稿，不实发 |
| 通知 | Bark / Webhook / ntfy / Telegram / Server酱 / 企业微信 |
| 登录 | 扫码 / Cookie |
| 设置 | 多厂商 AI 与自动回复档位 |

## 通知

在「通知」页添加渠道后，盯盘命中或登录失效会推送，也可点「测试推送」。

| 类型 | Endpoint |
|---|---|
| Bark | key 或 `https://api.day.app/{key}` |
| Webhook | 任意 URL，POST `{title, body, payload}` |
| ntfy | `https://ntfy.sh/主题` 或 `token 主题` |
| Telegram | `bot_token\|chat_id` |
| Server酱 | SendKey |
| 企业微信 | 机器人 key 或完整 webhook URL |

同一商品 12 小时内不会重复推。登录失效 6 小时内只提醒一次。

## AI

设置里选厂商，或把 Base URL 交给「自动识别」。支持：

OpenAI、DeepSeek、Ollama 本地、Anthropic Claude、Azure OpenAI、Gemini、Groq、OpenRouter、通义千问、Kimi、智谱、硅基流动、Together、MiniMax、零一万物，以及任意 OpenAI 兼容端点。

Ollama 默认不用 Key。其它厂商不配 Key 时，AI 页仍可用本机样本做粗判。价格统计不是全网官方行情。

## 自动回复

设置里只有「关闭 / 草稿」。命中规则后写入草稿日志，并在私信页提示，**不会自动发给对方**。

## 主要 API

- `POST /search/` → 含 `items`
- `GET /products`、`GET /products/stats?q=`
- `CRUD /watches`、`POST /watches/{id}/run`
- `CRUD /notify/channels`、`GET /notify/kinds`、`POST /notify/test`
- `POST /ai/chat`、`GET /ai/providers`、`GET/PUT /settings`
- `CRUD /autoreply/rules`
- 原有 `/auth/*`、`/im/*`

## 开发

```bash
python spider.py --port 8000
cd frontend && npm install && npm run dev
```

数据与密钥在 `data/`（已 gitignore）。

## 说明

- 引擎单机常开；以后手机壳只连这台引擎。
- 价格统计基于本机样本。
- 仅供学习研究，请遵守闲鱼与当地法规。
