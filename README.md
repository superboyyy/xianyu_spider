# 闲鱼工作台 API

本机闲鱼引擎：搜货、货架、盯盘推送、AI 问询、私信与自动回复（HTTP API）。

## 快速开始

```bash
pip install -r requirements.txt
playwright install chromium   # 扫脸认证需要

python spider.py
```

打开 http://127.0.0.1:8000/docs

## 主要 API

- `POST /search/` → 含 `items`
- `GET /products`、`GET /products/stats?q=`
- `CRUD /watches`、`POST /watches/{id}/run`
- `CRUD /notify/channels`、`POST /notify/test`
- `POST /ai/chat`、`GET/PUT /settings`
- `CRUD /autoreply/rules`
- 原有 `/auth/*`、`/im/*`

## 通知（Bark）

`POST /notify/channels` 添加渠道，Endpoint 填 Bark key 或 `https://api.day.app/{key}`。盯盘触发后会推送；也可 `POST /notify/test`。

## AI

`PUT /settings` 填 `ai_base_url`（默认 DeepSeek）和 API Key。不配 Key 时，AI 接口仍可用本机样本做粗判。

## 说明

- 引擎单机常开；数据与密钥在 `data/`（已 gitignore）。
- 价格统计基于本机样本，不是全网官方行情。
- 自动回复默认建议「草稿」。
- 仅供学习研究，请遵守闲鱼与当地法规。
