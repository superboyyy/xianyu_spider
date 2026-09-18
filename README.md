# 闲鱼工作台

本机闲鱼引擎 + 液态玻璃 Web 客户端（Vue 3）。支持搜货、货架、盯盘推送、AI 问询、私信与自动回复。

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
| 自动回复 | 规则；设置里选关闭 / 草稿 / 实发 |
| 通知 | Bark / Webhook |
| 登录 | 扫码 / Cookie |
| 设置 | AI Key（OpenAI 兼容）与自动回复档位 |

## 通知（Bark）

在「通知」页添加渠道，Endpoint 填 Bark key 或 `https://api.day.app/{key}`。盯盘触发后会推送；也可点「测试推送」。

## AI

设置里填 `AI Base URL`（默认 DeepSeek）和 API Key。不配 Key 时，AI 页仍可用本机样本做粗判。

## 主要 API

- `POST /search/` → 含 `items`
- `GET /products`、`GET /products/stats?q=`
- `CRUD /watches`、`POST /watches/{id}/run`
- `CRUD /notify/channels`、`POST /notify/test`
- `POST /ai/chat`、`GET/PUT /settings`
- `CRUD /autoreply/rules`
- 原有 `/auth/*`、`/im/*`

## 开发

```bash
# 后端
python spider.py --port 8000

# 前端热更新（另开终端）
cd frontend && npm install && npm run dev
```

数据与密钥在 `data/`（已 gitignore）：`xianyu.sqlite3`、`session.json`、`keys.json`、`settings.json`。

## 说明

- 引擎单机常开；以后手机壳只连这台引擎。
- 价格统计基于本机样本，不是全网官方行情。
- 自动回复默认建议「草稿」。
- 仅供学习研究，请遵守闲鱼与当地法规。
