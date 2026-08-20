# 闲鱼商品搜索API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.68.0-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)

基于 FastAPI 构建的闲鱼商品搜索接口，支持异步并发请求和自动化数据去重存储。现已支持登录。

## 功能特性

- 🔍 关键词商品搜索（支持分页、排序、价格和地区筛选）
- ⚡ 异步高性能爬取（HTTP 直连搜索接口，默认按最新发布排序）
- 🔐 支持扫码登录和扫脸认证
- 🛡️ 智能数据去重（基于链接特征哈希值）
- 💾 数据持久化存储（关系数据库）
- 📊 返回新增记录统计信息，以及当前是否登录态

## 技术栈

| 组件           | 用途                     |
|----------------|--------------------------|
| FastAPI        | RESTful API框架          |
| httpx          | 异步 HTTP 搜索 / 登录请求 |
| Playwright     | 扫脸认证                 |
| Tortoise ORM   | 异步数据库ORM            |
| SQL            | 数据持久化存储           |
| Uvicorn        | ASGI服务器               |

## 快速开始

### 环境配置

1. 安装依赖
```bash
pip install -r requirements.txt
playwright install chromium   # 扫脸认证需要，安装一次即可
```

2. 创建 `.env` 文件（可选；不配的话默认用 `data/xianyu.sqlite3`）
```env
DATABASE_URL=mysql://user:password@localhost/xianyu
```

### 启动服务
```bash
python spider.py
```

### 登录

```bash
python spider.py login
```

终端会显示登录二维码。扫码确认后，如需扫脸认证会自动打开浏览器完成。

也可以：

```bash
python spider.py login --cookie    # 粘贴已登录网页的 Cookie
python spider.py login --browser   # 直接打开官方登录页
```

登录态保存在 `data/session.json`，可通过 `GET /auth/status` 查询。

### 搜索

```bash
python spider.py search 手机 --pages 3
python spider.py search 相机 --sort price_asc --min-price 100 --max-price 800 --city 深圳
python spider.py search 自行车 --no-save
```

已登录时会自动带上 `data/session.json`。默认写入数据库；`--no-save` 只打印 JSON。

## API 文档

访问 `http://localhost:8000/docs` 查看交互式文档

### 搜索接口
```
POST /search/
```

**请求参数示例**：
```json
{
  "keyword": "手机",
  "max_pages": 1,
  "sort": "newest",
  "min_price": 100,
  "max_price": 2000,
  "city": "深圳"
}
```

`sort` 可选：`newest`（默认，最新发布）、`price_asc`、`price_desc`、`default`（综合）。

**响应示例**：
```json
{
  "status": "success",
  "keyword": "手机",
  "logged_in": false,
  "user_id": "",
  "filters": {"sort": "newest", "min_price": 100, "max_price": 2000, "city": "深圳"},
  "total_results": 30,
  "new_records": 5,
  "new_record_ids": [101,102,103,104,105]
}
```

## 使用示例
建议使用 Apifox 或者 Postman 进行测试

### cURL 请求
```bash
curl -X POST "http://localhost:8000/search/" \
-H "Content-Type: application/json" \
-d '{"keyword": "笔记本电脑", "max_pages": 2}'
```

### Python 客户端
```python
import requests

response = requests.post(
    "http://localhost:8000/search/",
    json={"keyword": "数码相机", "max_pages": 3}
)
print(response.json())
```

## 注意事项

1. **法律合规**  
使用前请确保遵守《网络安全法》和闲鱼平台 Robots 协议，本代码仅用于学习研究

2. **反爬机制**  
建议配置代理 IP 池和随机请求间隔，默认配置可能触发反爬限制

3. **性能调优**  
- 调整数据库连接池配置（`pool_recycle`等参数）
- 建议生产环境部署时增加 Redis 缓存层

## 交流与贡献

欢迎贡献，也欢迎友善交流：https://t.me/+fHzEZCAdSwA0NTZl

## 版权声明

本项目采用 [MIT License](LICENSE)，请合理使用并注明出处。数据抓取结果不得用于商业用途。
