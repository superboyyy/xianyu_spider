# 闲鱼商品搜索API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.68.0-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)

基于 FastAPI 构建的闲鱼商品搜索接口，支持异步并发请求和自动化数据去重存储。

## 功能特性

- 🔍 关键词商品搜索（支持分页）
- ⚡ 异步高性能爬取（Playwright 无头浏览器）
- 🛡️ 智能数据去重（基于链接特征哈希值）
- 💾 数据持久化存储（默认 SQLite，可选 MySQL）
- 📊 返回商品明细和新增记录统计信息

## 技术栈

| 组件           | 用途                     |
|----------------|--------------------------|
| FastAPI        | RESTful API框架          |
| Playwright     | 浏览器自动化爬取         |
| Tortoise ORM   | 异步数据库ORM            |
| SQLite / MySQL | 数据持久化存储           |
| Uvicorn        | ASGI服务器               |

## 快速开始

### 环境配置

1. 安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

2. 可选：创建 `.env` 文件

默认会使用当前目录下的 SQLite 文件 `xianyu.db`，无需额外配置。若要改用 MySQL：

```env
DATABASE_URL=mysql://user:password@localhost/xianyu
```

### 启动服务
```bash
python spider.py
```

## API 文档

访问 `http://localhost:8000/docs` 查看交互式文档

健康检查：`GET /health`

### 搜索接口
```
POST /search/
```

**请求参数示例**：
```json
{
  "keyword": "手机",
  "max_pages": 1
}
```

**响应示例**：
```json
{
  "status": "success",
  "keyword": "手机",
  "total_results": 30,
  "new_records": 5,
  "new_record_ids": [101,102,103,104,105],
  "items": [
    {
      "id": 101,
      "title": "iPhone 14 Pro 128G 黑色",
      "price": "¥2499",
      "area": "广东",
      "seller": "示例卖家",
      "link": "https://www.goofish.com/item?id=123",
      "image_url": "https://img.alicdn.com/example.jpg",
      "publish_time": "2026-08-18 15:00",
      "is_new": true
    }
  ]
}
```

`items` 是本次搜到的全部商品明细。`id` 为数据库主键；`is_new` 为 `true` 表示这次新写入，`false` 表示库里已有相同链接。发布时间未知时 `publish_time` 为 `null`。

## 使用示例

建议使用 Apifox 或者 Postman 进行测试。

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

### 命令行导出 Excel
```bash
XIANYU_KEYWORD=手机 XIANYU_PAGES=1 python test.py
```

未设置环境变量时，脚本会交互式询问关键词和页数。有桌面目录则保存到桌面，否则保存到当前目录。

## 当前站点适配说明（2026-08）

对 `www.goofish.com` 实测后的结论：

- 搜索接口 `mtop.taobao.idlemtopsearch.pc.search` 仍可用，商品 JSON 结构未变。
- 页面仍会弹出登录框；脚本会先关掉可关闭的登录/广告遮罩，再继续搜索。
- 未登录时默认搜索结果仍可采集；「新发布 / 最新」排序若被弹窗挡住会自动跳过，不中断整次任务。
- 直接访问搜索 URL 更容易触发闲鱼风控（`RGV587` / 滑动验证），因此仍从首页输入关键词搜索。

## 注意事项

1. **法律合规**  
使用前请确保遵守《网络安全法》和闲鱼平台 Robots 协议，本代码仅用于学习研究。

2. **反爬机制**  
默认配置可能触发登录弹窗或验证码。请控制频率，不要把本项目用于绕过平台限制或商业采集。

3. **性能调优**  
- 调整数据库连接池配置（`pool_recycle` 等参数）
- 建议生产环境部署时增加 Redis 缓存层

## 版权声明

本项目采用 [MIT License](LICENSE)，请合理使用并注明出处。数据抓取结果不得用于商业用途。
