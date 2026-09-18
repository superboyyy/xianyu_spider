# 闲鱼工作台：前后端方案

本文只定方案，不改业务代码。落地时按文末阶段拆 PR，不要一次把搜货、盯盘、AI、自动回复全塞进同一个提交。

参考视觉：[omusic.plus](https://omusic.plus/zh-cn/) 的液态玻璃官网。参考能力：本仓库现有 FastAPI 引擎（搜索 / 扫码登录 / 闲鱼 IM）。

---

## 0. 结论

**后端必须改。** 现有 API 能搜、能登录、能收发私信，但搜货不返回商品明细，也没有货架查询、定时盯盘、推送、AI 问询、自动回复。前端无法只靠现有接口做出可用工作台。

**前端从零做。** 仓库目前没有 Web 客户端。`python spider.py` 之后打开 `http://127.0.0.1:8000` 应直接进入本机工作台，命令行和 `/docs` 继续保留。

**形态：单机引擎 + 浏览器壳。** FastAPI 仍是事实源。登录 Cookie、SQLite、盯盘调度都在本机。以后手机壳只连这套 HTTP，不必再写第二套业务。

**价格统计只基于本机样本。** 均价 / 中位 / 「是否入手」都要带免责声明，不是闲鱼官方行情。

---

## 1. 现状与缺口

### 1.1 已经有的

| 能力 | 入口 | 说明 |
|---|---|---|
| 关键词搜索 | `POST /search/` | 支持排序、价格、省市、`publish_days`；结果写入 `xianyu_products` |
| 登录 | `/auth/*`、`python spider.py login` | 扫码、拍脸、Cookie；态在 `data/session.json` |
| 登录探测 | `GET /auth/status` | Cookie 失效时搜索仍按未登录继续 |
| 私信 | `/im/*` | 长连接、本地会话、SSE `message.received` / `message.sent` |
| 命令行 | `spider.py search` | 与 HTTP 共用同一套筛选 |

数据表只有两张：`xianyu_products`、`im_messages`。

### 1.2 前端立刻撞上的缺口

1. **`POST /search/` 不返回商品列表。** 只有 `total_results` / `new_records` / `new_record_ids`。页面没法画卡片。
2. **没有货架读取接口。** 商品进了库，外面读不出来。
3. **IM 注释写明「不接 webhook / 自动回复」。** 收信后不会草稿、不会实发。
4. **没有定时任务、没有推送、没有 AI。**
5. **搜索响应仍是中文字段**（`商品标题` / `当前售价`）。前端、盯盘、AI 工具应共用一份英文 DTO。

### 1.3 明确不做

- 不做多租户 SaaS，不做云端代登录。
- 不做秒拍、自动议价、批量骚扰卖家。
- 不把 Cookie / API Key 送到浏览器以外。
- 不和网页版闲鱼 IM 同时开（token 会互踢，现有 README 已写）。
- 不承诺全网真实成交价。

---

## 2. 产品对照

把 omusic.plus 的「曲库工作台」映射到闲鱼本机工作台，而不是做成营销落地页。

| omusic.plus | 本工作台 | 用户动作 |
|---|---|---|
| 搜索曲库 | 搜货 | 关键词 + 筛选，立刻看到卡片 |
| 本地资料库 | 货架 | 翻已落库商品，断网也能看 |
| 歌单 / 订阅 | 盯盘任务 | 定时搜，上新 / 低价推到手机 |
| 听歌统计 | 价格样本 | 均价、中位、最低、样本数 |
| 智能推荐 | AI 问询 | 找货、判断入手、起草私信 |
| 歌词 / 正在播放 | 私信 | 登录后收发文本 |
| 睡眠定时 | 自动回复档位 | 关闭 / 草稿 / 实发 |
| 设置与订阅源 | 通知渠道 + 模型 | Bark 等；OpenAI 兼容 Key |

一句话：左边玻璃导航，中间沉浸式内容，商品图当封面，品红强调操作。

---

## 3. 整体架构

```
浏览器工作台 (Vue 3, Hash 路由)
        │  REST + SSE
        ▼
FastAPI 单机引擎  ──  闲鱼 mtop / IM WS
        │
        ├── 搜索 / 货架 / 价格样本
        ├── 盯盘调度 (进程内 tick)
        ├── 通知适配器 (Bark / Webhook / …)
        ├── AI 工具循环 (search / stats / recommend / draft_im)
        └── 自动回复 (规则优先，默认草稿)
        │
        ▼
SQLite (data/xianyu.sqlite3) + session.json + keys.json
```

部署假设：本机常开 `python spider.py`。开发时前端 `vite` 代理到 `:8000`；发布时构建进 `web/`，由 FastAPI 挂 `/`。

---

## 4. 前端方案

### 4.1 技术选型

| 项 | 选择 | 原因 |
|---|---|---|
| 框架 | Vue 3 + Vue Router + Vite | 页面状态简单，不必上 Pinia 全家桶；一个 `api.js` 即可 |
| 路由 | `createWebHashHistory` | 后端只挂静态目录，刷新不 404 |
| 样式 | 自研 token + 玻璃组件，不引 Element / Tailwind | 对齐 omusic.plus，避免组件库皮肤打架 |
| 实时 | `EventSource('/im/events')` | 已有 SSE，私信页直接用 |
| 产物 | 源码 `frontend/`，构建 `web/` | **不要把巨大 hashed bundle 当主源码提交**；用 `npm run build && 同步到 web/` 脚本 |

开发：

```bash
python spider.py --port 8000
cd frontend && npm install && npm run dev   # vite → proxy /api 到 8000
```

生产：打开 `http://127.0.0.1:8000` 就是工作台。`/docs` 仍是 OpenAPI。

### 4.2 视觉系统（对齐 omusic.plus）

官网关键词：液态玻璃、通透、细腻、暗红到品红的流动背景、大标题、胶囊按钮。

**Token（落地时写入 `frontend/src/styles/tokens.css`）：**

| Token | 值 | 用途 |
|---|---|---|
| `--accent` | `#fa2d48` | 主按钮、品牌标、焦点 |
| `--accent-soft` | `#fc3c6e` | 渐变另一端 |
| `--hero-base` | `#12010a` | 深酒红底 |
| `--text` | `#f5f5f7` | 主文案 |
| `--text-dim` | `#a1a1a6` | 辅文案 |
| `--glass-bg` | `rgba(255,255,255,0.06)` | 卡片 |
| `--glass-border` | `rgba(255,255,255,0.12)` | 描边 |
| `--font` | SF Pro / PingFang SC / 系统黑体 | 与官网一致 |
| `--ease` | `cubic-bezier(0.28, 0.11, 0.32, 1)` | 过渡 |
| `--radius-card` | `22px` | 玻璃卡 |
| `--radius-pill` | `980px` | 按钮 |

**背景：** 多层径向光斑（品红 `#ff2d55`、珊瑚 `#ff8a3d`）缓慢流动，尊重 `prefers-reduced-motion`。

**玻璃卡：** `backdrop-filter: blur(18px) saturate(150%)` + 内高光，不做折射/色散（性能差、难维护）。

**商品卡 = 专辑封面：** 方图铺满上半，标题两行截断，价格用强调色大号，地区/卖家/时间用 dim 字。悬停轻微上浮。

**导航：** 左侧 240px 玻璃轨；窄屏改底部 Tab（搜货 / 货架 / 盯盘 / 私信 / 更多）。

**顶栏状态芯片：** 登录态、IM 在线、盯盘是否在跑。失效登录用警示色，不打断搜货。

### 4.3 信息架构

```
/search      搜货     默认首页
/shelf       货架
/watches     盯盘
/ai          AI 问询
/inbox       私信
/autoreply   自动回复
/notify      通知
/login       登录
/settings    设置
```

九个入口可以存在，但首屏只突出四个：搜货、货架、盯盘、AI。私信 / 自动回复 / 通知 / 登录放「更多」或轨底部，避免做成九宫格后台。

### 4.4 页面规格

#### 搜货 `/search`

- 筛选：关键词、最低/最高价、省、市、最近 N 天、排序（最新 / 低价 / 高价 / 综合）、页数。
- 主按钮「搜索」。结果区玻璃网格。
- 卡片操作：打开闲鱼链接、加入盯盘（预填关键词+目标价）、问 AI「这个值不值」。
- 结果带来的 `is_new` 打「新」标。
- 空态、加载、失败、登录失效（横幅，不挡结果）都要有。
- **依赖后端：`POST /search/` 必须带 `items`。**

#### 货架 `/shelf`

- `GET /products?q=&limit=&offset=`。
- 本地筛选标题；可选展示当前页价格样本（均/中/最低）。
- 点进详情抽屉：图、价、卖家、发布时间、历史快照（有盯盘才有）。

#### 盯盘 `/watches`

- 列表：关键词、间隔、上次运行、上次错误、开关。
- 新建/编辑：与搜索相同的筛选 + `interval_minutes`（建议下限 10）+ 通知开关：
  - 上新 `notify_new`
  - 低于目标价 `target_price`
  - 低于样本中位 N% `notify_below_median_pct`
- 手动「跑一次」。
- 运行记录：命中条数、触发了哪类通知。
- 文案写清：间隔过短容易被闲鱼限流。

#### AI `/ai`

- 对话线程。用户自然语言，例如：
  - 「帮我找深圳 2000 以内的 X100VI」
  - 「索尼头层牛皮公文包均价/中位多少」
  - 「这个链接 / 这个货值不值」
  - 「帮我起草一句还在吗」
- 回复里嵌商品卡和统计卡，并固定页脚：「基于本机样本，不是全网官方行情」。
- 无 API Key 时仍可用本地启发式（见后端），页面提示「离线粗判」。
- 工具调用过程用一条「正在搜货 / 正在算中位」的玻璃提示，不要空白转圈。

#### 私信 `/inbox`

- 左会话、右消息。连接按钮调 `POST /im/start`。
- SSE 追加新消息。发送走 `POST /im/send`。
- 未登录 / 未 start 的 401、409 显示成人话，不要白屏。
- 顶栏提示：不要和网页版同时开。

#### 自动回复 `/autoreply`

- 规则：匹配文本、回复文本、冷却秒、仅首条。
- 日志：草稿 / 已发 / 失败。
- 档位在设置里：`off` / `draft` / `send`。**默认 `off`，推荐 `draft`。**
- `send` 要二次确认。

#### 通知 `/notify`

- 渠道 CRUD。P0：Bark、通用 Webhook。
- Endpoint 接受 Bark key 或 `https://api.day.app/{key}`。
- 测试推送、最近事件（成功/跳过去重/失败原因）。

#### 登录 `/login`

- 已有扫码、拍脸、Cookie、本机浏览器验证，做成同一套玻璃页。
- 轮询 `GET /auth/qr/status`。成功后芯片变「已登录」。
- 不在前端存 Cookie 明文。

#### 设置 `/settings`

- AI Base URL / Model / API Key（回显脱敏）。
- 自动回复档位。
- 盯盘最短间隔（可选）。

### 4.5 前端状态

不强制 Pinia。建议：

- `App.vue`：`auth`、`im` 两个 reactive，30s 刷新 + 登录成功后立刻刷新。
- 各页自己拉列表。
- `api(path, opts)` 统一处理 JSON / 错误 `detail`。
- 商品卡抽 `ProductCard.vue`，搜货 / 货架 / AI / 盯盘命中共用。

### 4.6 前端文件

```
frontend/
  index.html
  package.json
  vite.config.js          # /auth /search /im /products … 代理到 :8000
  src/main.js
  src/App.vue
  src/router.js
  src/api.js
  src/styles/tokens.css
  src/styles/glass.css
  src/styles/app.css
  src/components/ProductCard.vue
  src/components/StatChip.vue
  src/views/*.vue
web/                      # 构建产物，只在发布脚本里更新
```

### 4.7 前端验收

用浏览器走通，不是只截一张静态图：

1. 未登录打开 `/` → 搜货页，能搜到卡片（依赖后端返回 `items`）。
2. 登录页能出码；Cookie 导入成功后芯片变化。
3. 货架能看到刚才落库的商品。
4. 私信：未登录点连接不崩；已登录能看到本地历史。
5. 窄屏（390px）导航可用，卡片不溢出。
6. 登录失效搜货仍出结果 + 横幅。

---

## 5. 后端方案

### 5.1 原则

- 搜索、登录、IM 协议层尽量不动。新能力做成新 router / 新表。
- 对外商品字段统一为 `catalog` DTO，中文原始字段只留在爬虫内部。
- 密钥进 `data/keys.json`（0600），不进 SQLite，不进 git。
- 盯盘调度在进程内即可（单机）。以后要独立 worker 再拆。
- 通知渠道用适配器，先 Bark + Webhook，接口预留 `kind`。

### 5.2 必须改的现有接口

#### `POST /search/` 增加 `items`

现有统计字段保持不变，避免命令行/旧客户端坏掉。

```json
{
  "status": "success",
  "keyword": "相机",
  "logged_in": false,
  "user_id": "",
  "filters": {"sort": "newest", "city": "深圳"},
  "total_results": 30,
  "new_records": 5,
  "new_record_ids": [101, 102],
  "items": [
    {
      "id": 101,
      "item_id": "8xxxxxxxxxx",
      "title": "…",
      "price": "¥1200",
      "area": "深圳",
      "seller": "…",
      "seller_id": "",
      "link": "https://www.goofish.com/item?id=…",
      "image_url": "https://…",
      "publish_time": "2026-09-18 12:00",
      "is_new": true
    }
  ]
}
```

`id` 是本机货架主键；`item_id` 从链接解析；`is_new` 表示这次刚插入。

实现：抽 `xianyu/catalog.py`（`public_from_raw` / `product_to_public` / `attach_saved_ids`）。现有 `test_app.py` 里断言统计字段的用例继续过，再补 `items` 断言。

### 5.3 新增模块与路由

| 模块 | 路由前缀 | 职责 |
|---|---|---|
| `xianyu/catalog.py` | — | 商品 DTO |
| `xianyu/pricing.py` | — | 解析 `¥1,200` / `1.2万`，算 min/max/avg/median |
| `xianyu/routers/products.py` | `/products` | 货架列表、详情、样本统计 |
| `xianyu/watch/` | `/watches` | 任务 CRUD、手动跑、运行日志、进程内调度 |
| `xianyu/notify/` | `/notify` | 渠道、测试、事件 |
| `xianyu/ai/` | `/ai` | 对话 + 工具循环 |
| `xianyu/autoreply/` | `/autoreply` | 规则、日志、档位 |
| `xianyu/secrets.py` | `/settings` | 本机设置与 Key |
| `xianyu/routers/spa.py` | `/` | 挂 `web/` 静态（无产物时 404 友好页） |

`xianyu/app.py`：注册新 router；lifespan 里 `scheduler.start()`；开发期可加 CORS。测试 `create_app(connect_xianyu=False)` **不要** 启动调度和闲鱼网络。

### 5.4 数据模型

在 `xianyu/models.py` 增表（`generate_schemas=True` 会建新表；旧表不要手改结构，IM 已有迁移函数）。

**`watches`**

- `name`, `keyword`, 与 `SearchFilters` 对齐的筛选字段
- `max_pages`（建议 ≤ 3）
- `interval_minutes`（默认 15，硬下限建议 10）
- `enabled`
- `notify_new`, `notify_below_target`, `target_price`, `notify_below_median_pct`
- `last_run_at`, `last_error`

**`watch_runs`**

- FK `watch`, `status`, `total_results`, `new_records`, `min_price`, `triggered` (JSON), `error`, `created_at`

**`price_snapshots`**

- `keyword`, `product_id`, `item_id`, `title`, `price_text`, `price_value`, `city`, `watch_id`, `created_at`
- 给均价 / 低于中位 / AI 统计用。不是每条搜索都强制写；盯盘必写，手动搜索可写。

**`notify_channels`**

- `name`, `kind` (`bark` | `webhook` | 预留 `serverchan` / `telegram` / `ntfy` / `wecom`), `endpoint`, `enabled`

**`notify_events`**

- `channel_id`, `event_type`, `fingerprint`, `title`, `body`, `payload`, `ok`, `error`, `created_at`
- `fingerprint` 用于 12h 去重，避免同一商品刷屏。

**`ai_threads` / `ai_messages`**

- 消息带 `role`、`content`、`refs`（挂上的商品 id / 统计）。

**`autoreply_rules` / `autoreply_logs`**

- 规则：`match_text`, `reply_text`, `cooldown_seconds`, `only_first`, `enabled`
- 日志：`conversation_id`, `incoming`, `reply`, `mode`, `status`

`ChatMessage.source` 允许 `user` / `gateway` / `rule` / `ai`（仅扩语义，不必迁表）。

### 5.5 API 契约

#### 货架

```
GET  /products?q=&limit=40&offset=0&stats=false
GET  /products/stats?q=关键词
GET  /products/{id}
```

`/products/stats` 合并货架标题匹配 + `price_snapshots`，返回：

```json
{
  "keyword": "X100VI",
  "count": 42,
  "min": 9800,
  "max": 14500,
  "avg": 11820,
  "median": 11600,
  "disclaimer": "基于本机货架与盯盘快照，不是全网官方行情"
}
```

样本不足（例如 `< 5`）时前端/AI 都要说「样本少，判断弱」。

#### 盯盘

```
GET    /watches
POST   /watches
PUT    /watches/{id}
DELETE /watches/{id}
POST   /watches/{id}/run
GET    /watches/{id}/runs
GET    /watches/scheduler
```

`POST /watches/{id}/run` 同步跑完再返回命中摘要（方便手动点一次就看到结果）。调度器 30s tick，到期才跑。同一时刻串行跑任务，避免把搜索打爆。

触发规则（任务配置，可组合）：

| `event_type` | 条件 | 推送标题例 |
|---|---|---|
| `new_listing` | 本次 `is_new` | 上新 · 关键词 |
| `below_target` | 解析价 ≤ `target_price` | 低价 · 关键词 |
| `below_median_pct` | 价 ≤ 中位 × (1 - N%) | 低于中位 · 关键词 |

去重键：`event_type + watch_id + item_id [+ 价格]`。12 小时内成功过的不再推。

#### 通知

```
GET    /notify/channels
POST   /notify/channels
PUT    /notify/channels/{id}
DELETE /notify/channels/{id}
POST   /notify/channels/{id}/test
GET    /notify/events?limit=50
```

**Bark：**

- 用户填 key 或完整 URL。
- `GET https://api.day.app/{key}/{title}/{body}`（已编码）。
- 以后要分组/铃声，再加 query，不改表。

**Webhook：**

- `POST endpoint`，JSON：`{title, body, payload}`。
- 用户自己接到 Server 酱 / ntfy / 企业微信 / Telegram bot 的转换层。

P1 可把这些 `kind` 做成一等适配器（仍只存 endpoint）：

| kind | 调用 |
|---|---|
| `bark` | GET path |
| `webhook` | POST JSON |
| `ntfy` | POST 文本，`Authorization` 可选 |
| `telegram` | `https://api.telegram.org/bot<token>/sendMessage` |
| `serverchan` | Server 酱 SendKey |
| `wecom` | 企业微信机器人 key |

P0 只做前两个，前端 `kind` 下拉先开放 `bark` / `webhook`。

#### AI

```
GET  /ai/threads
POST /ai/chat          { "message", "thread_id?" }
GET  /ai/threads/{id}
```

工具（模型 function calling）：

| 工具 | 作用 | 副作用 |
|---|---|---|
| `search_items` | 调现有 HTTP 搜索 | 会写货架 |
| `price_stats` | 本机均价/中位 | 只读 |
| `recommend` | 按预算+中位打分，`buy` / `wait` / `skip` | 只读 |
| `draft_im` | 起草私信 | **不发送** |

系统提示必须写：样本局限、不编造未搜到的商品、不主动实发私信。

无 Key：走同一套 `price_stats` + `recommend` 启发式，返回 `provider: "offline"`。有 Key：OpenAI 兼容（默认 DeepSeek `https://api.deepseek.com/v1`），最多 3 轮工具循环。

`recommend` 启发式（无模型时也用）：

- 基准 60 分。
- 低于中位 15%：+20；高于中位 15%：-15。
- 在预算内且 ≤ 90% 预算：+10；超预算：直接排除。
- 无图：-5。
- `≥75 buy` / `≥55 wait` / 其余 `skip`。
- 标题过短、样本 `<5`：强制降为 `wait`。

#### 自动回复

```
GET/POST/PUT/DELETE /autoreply/rules
GET  /autoreply/logs
```

档位在 `GET/PUT /settings` 的 `autoreply_mode`。

收信挂钩：`IMService._on_incoming` 入库并 SSE 之后，调用 `maybe_autoreply`。只处理 `direction=in`。规则按列表顺序，第一条命中即停。冷却 / `only_first` 看日志表。

- `off`：什么都不做。
- `draft`：写日志 + SSE `autoreply.draft`，不调用 `send_text`。
- `send`：`send_text(..., source="rule")`。

默认 `off`。

#### 设置

```
GET /settings          # Key 脱敏，只给 has_ai_api_key
PUT /settings          # ai_base_url / ai_model / ai_api_key / autoreply_mode
```

### 5.6 调度与风控

- 调度 tick 30s；任务间隔默认 15 分钟，最小值 10。
- 同时只跑一个 `run_watch`。
- `max_pages` 默认 1。
- 搜索失败写入 `last_error` 和 `watch_runs`，不要把整个调度打死。
- 登录失效：盯盘仍按未登录搜，并推一条 `login_expired`（去重 6h），提醒去登录页。

### 5.7 静态资源

`app.mount("/", StaticFiles(directory=web, html=True))` 必须放在 API 路由之后。没有 `web/index.html` 时返回简短说明：先构建前端或用 vite。不要让挂载吃掉 `/docs`。

### 5.8 后端测试

现有 pytest 保持绿。新增：

- `tests/test_catalog.py`：中英字段、`item_id` 解析、`is_new`。
- `tests/test_pricing.py`：`¥1.2万`、空价、中位数偶数个。
- `tests/test_watch_notify_ai.py`：盯盘触发、Bark URL 拼接（httpx mock）、去重、无 Key 的 AI 粗判、自动回复草稿不发送。
- 现有 `test_app.py`：搜索响应仍含旧字段，并含 `items`。

不在 CI 打真实闲鱼、不打真实 Bark。

---

## 6. 关键时序

### 6.1 搜货

```
页面 POST /search/
  → probe_login()
  → scrape_xianyu_http()
  → catalog.public_from_raw()
  → save_to_db()
  → attach_saved_ids()
  → { …旧字段, items }
```

### 6.2 盯盘命中推送

```
scheduler tick
  → run_watch
  → 搜索 + 落库 + price_snapshots
  → evaluate_triggers
  → fingerprint 去重
  → 每个 enabled channel（Bark / Webhook）
  → notify_events
```

### 6.3 AI 问「值不值」

```
POST /ai/chat
  → 若有 Key：模型决定调 search_items / price_stats / recommend
  → 若无 Key：直接 stats + recommend
  → 回复 + refs[] 商品卡
```

### 6.4 自动回复

```
IM 推送
  → 入库 + SSE message.received
  → maybe_autoreply
  → draft：SSE autoreply.draft
     send：send_text + message.sent
```

---

## 7. 分阶段落地（按这个拆 PR）

上一轮把 Vue + 盯盘 + Bark + AI 打成一个大包，难审。按阶段合并：

### P0 — 能看见货

**后端：** `catalog` + `POST /search/` 返回 `items` + `GET /products` + `GET /products/{id}`。

**前端：** 玻璃壳 + 搜货 + 货架 + 登录（复用现有 `/auth`）。FastAPI 挂 `web/`。

**验收：** 浏览器搜「手机」出卡片；货架能翻到；登录页能出码。

### P1 — 私信

**后端：** 基本不用改；SSE 事件原样给前端。

**前端：** `/inbox` 连接、列表、发送、空态/401/409。

### P2 — 盯盘 + 通知

**后端：** watches / snapshots / notify（Bark + Webhook）+ 进程内调度。

**前端：** `/watches`、`/notify`。

**验收：** 建任务 → 手动跑 → 测试 Bark（mock 或用户自己的 key）→ 事件表有记录。去重要测。

### P3 — AI 问询

**后端：** `/ai/chat` 工具循环；`/products/stats`；`/settings`。

**前端：** `/ai` 对话 + 商品卡/统计卡。

**验收：** 无 Key 能粗判；有 Key（测试用 mock LLM）会调工具。

### P4 — 自动回复

**后端：** 规则 + 档位 + IM 挂钩。

**前端：** `/autoreply`。默认 off，send 二次确认。

### P5 — 增强（需要再说一声再做）

- ntfy / Telegram / Server 酱 / 企业微信一等渠道
- 价格折线图
- 从搜货一键「按这个条件盯盘」
- 商品详情里的快照历史
- 多账号（现在是单 session，不做）

---

## 8. 风险

| 风险 | 处理 |
|---|---|
| 闲鱼限流 / 风控 | 盯盘间隔下限、串行、页数限制；失败记日志不崩溃 |
| Cookie 过期 | 已有探测；搜货继续匿名；盯盘推 `login_expired` |
| IM 与网页互踢 | UI 和 README 写清楚 |
| 价格误导 | 强制 disclaimer；样本少降级 |
| 自动回复误发 | 默认关；推荐草稿；冷却；send 确认 |
| Key 泄漏 | `data/keys.json` gitignore + 0600；接口脱敏 |
| 玻璃模糊性能 | 不做折射；弱设备可关 blur |
| 静态挂载吃掉 API | mount 放最后；`/docs` 保持 |

合规：沿用 README，仅学习研究，遵守闲鱼规则与当地法律。本方案不增加绕过风控或未授权访问的能力。

---

## 9. 建议目录（落地后）

```
frontend/                 # Vue 源码
web/                      # 构建产物（发布脚本更新）
docs/workbench-plan.md    # 本文件
xianyu/catalog.py
xianyu/pricing.py
xianyu/secrets.py
xianyu/watch/
xianyu/notify/
xianyu/ai/
xianyu/autoreply/
xianyu/routers/products.py
xianyu/routers/watches.py
xianyu/routers/notify.py
xianyu/routers/ai.py
xianyu/routers/autoreply.py
tests/test_catalog.py
tests/test_watch_notify_ai.py
```

`requirements.txt` 在 P3 前不必加新包（httpx 已有）。前端依赖只在 `frontend/package.json`。

---

## 10. 给审阅的决定项

实现 P0 前希望确认这三件，避免再做一个难审的大包：

1. **阶段：** 默认先做 P0（能看见货的玻璃工作台）。还是 P0+P1+P2 一起（搜货+私信+Bark 盯盘）？
2. **AI 提供商：** 默认 DeepSeek OpenAI 兼容，Key 本机填。是否要一开始就兼容官方 OpenAI / 本地 Ollama？
3. **自动回复：** 第一期是否只做草稿，实发放到 P4？

没有新回复的话，按 **P0 → P1 → P2 → P3 → P4** 这个顺序做，AI 默认 DeepSeek 兼容，自动回复第一期只做草稿档。
