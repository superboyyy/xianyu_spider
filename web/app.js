const views = {
  search: { title: "搜货", lede: "按关键词、价格和地区抓取闲鱼，结果会写入本机货架。" },
  shelf: { title: "货架", lede: "已经落库的商品。搜索过的东西都在这里，断网也能翻。" },
  inbox: { title: "私信", lede: "登录后连接闲鱼 IM。不要和网页版同时开，会互相踢掉。" },
  login: { title: "登录", lede: "扫码、拍脸或粘贴 Cookie。登录态只保存在这台机器上。" },
};

const state = {
  view: "search",
  auth: { logged_in: false, user_id: "", login_expired: false, hint: "" },
  im: { running: false, connected: false, user_id: "", last_error: "" },
  search: {
    keyword: "",
    max_pages: 1,
    sort: "newest",
    min_price: "",
    max_price: "",
    city: "",
    publish_days: "",
    items: [],
    stats: null,
    error: "",
    busy: false,
  },
  shelf: { q: "", items: [], total: 0, error: "" },
  inbox: {
    conversations: [],
    messages: [],
    active: "",
    draft: "",
    error: "",
    notice: "",
  },
  login: {
    sessionId: "",
    qr: "",
    verifyQr: "",
    hint: "",
    cookie: "",
    busy: false,
    error: "",
  },
};

let qrTimer = 0;
let events = null;

function $(sel, root = document) {
  return root.querySelector(sel);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await res.text();
  let body = {};
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = { detail: text };
  }
  if (!res.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail || body));
  }
  return body;
}

async function refreshAuth() {
  state.auth = await api("/auth/status");
}

async function refreshIm() {
  state.im = await api("/im/status");
}

function setView(view) {
  state.view = views[view] ? view : "search";
  location.hash = state.view;
  if (state.view === "shelf") loadShelf();
  if (state.view === "inbox") loadInbox();
  render();
}

async function runSearch(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  state.search.keyword = String(form.get("keyword") || "").trim();
  state.search.max_pages = Number(form.get("max_pages") || 1);
  state.search.sort = String(form.get("sort") || "newest");
  state.search.min_price = String(form.get("min_price") || "");
  state.search.max_price = String(form.get("max_price") || "");
  state.search.city = String(form.get("city") || "").trim();
  state.search.publish_days = String(form.get("publish_days") || "");
  if (!state.search.keyword) {
    state.search.error = "先写一个关键词。";
    render();
    return;
  }
  state.search.busy = true;
  state.search.error = "";
  render();
  try {
    const payload = {
      keyword: state.search.keyword,
      max_pages: state.search.max_pages,
      sort: state.search.sort,
    };
    if (state.search.min_price) payload.min_price = Number(state.search.min_price);
    if (state.search.max_price) payload.max_price = Number(state.search.max_price);
    if (state.search.city) payload.city = state.search.city;
    if (state.search.publish_days) payload.publish_days = Number(state.search.publish_days);
    const body = await api("/search/", { method: "POST", body: JSON.stringify(payload) });
    state.search.items = body.items || [];
    state.search.stats = body;
    await refreshAuth();
  } catch (err) {
    state.search.error = err.message;
  } finally {
    state.search.busy = false;
    render();
  }
}

async function loadShelf() {
  try {
    const query = state.shelf.q ? `?q=${encodeURIComponent(state.shelf.q)}` : "";
    const body = await api(`/products${query}`);
    state.shelf.items = body.items || [];
    state.shelf.total = body.total || 0;
    state.shelf.error = "";
  } catch (err) {
    state.shelf.error = err.message;
  }
  render();
}

async function loadInbox() {
  try {
    await refreshIm();
    state.inbox.conversations = await api("/im/conversations");
    if (state.inbox.active) {
      state.inbox.messages = await api(
        `/im/messages?conversation_id=${encodeURIComponent(state.inbox.active)}`
      );
    }
    state.inbox.error = "";
  } catch (err) {
    state.inbox.error = err.message;
  }
  render();
}

function listenIm() {
  if (events) events.close();
  events = new EventSource("/im/events");
  events.onmessage = (event) => {
    try {
      const item = JSON.parse(event.data);
      if (item.event === "connected") return;
      if (item.conversation_id && item.conversation_id === state.inbox.active) {
        loadInbox();
      } else {
        api("/im/conversations").then((rows) => {
          state.inbox.conversations = rows;
          render();
        });
      }
    } catch {
      /* ignore malformed frames */
    }
  };
}

async function startIm() {
  try {
    await api("/im/start", { method: "POST" });
    listenIm();
    state.inbox.notice = "IM 已连接。只保留本次连上之后的文本。";
    await loadInbox();
  } catch (err) {
    state.inbox.error = err.message;
    render();
  }
}

async function stopIm() {
  await api("/im/stop", { method: "POST" });
  if (events) events.close();
  events = null;
  await loadInbox();
}

async function openConversation(id) {
  state.inbox.active = id;
  await loadInbox();
}

async function sendMessage(event) {
  event.preventDefault();
  const text = state.inbox.draft.trim();
  if (!text || !state.inbox.active) return;
  try {
    await api("/im/send", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: state.inbox.active,
        to_user_id: state.inbox.active,
        text,
        source: "user",
      }),
    });
    state.inbox.draft = "";
    await loadInbox();
  } catch (err) {
    state.inbox.error = err.message;
    render();
  }
}

async function startQr() {
  state.login.busy = true;
  state.login.error = "";
  render();
  try {
    const body = await api("/auth/qr/start", { method: "POST" });
    state.login.sessionId = body.session_id || "";
    state.login.qr = body.qr_image_base64 || "";
    state.login.verifyQr = "";
    state.login.hint = body.hint || body.message || "";
    pollQr();
  } catch (err) {
    state.login.error = err.message;
  } finally {
    state.login.busy = false;
    render();
  }
}

function pollQr() {
  window.clearInterval(qrTimer);
  if (!state.login.sessionId) return;
  qrTimer = window.setInterval(async () => {
    try {
      const body = await api(`/auth/qr/status?session_id=${encodeURIComponent(state.login.sessionId)}`);
      state.login.hint = body.hint || "";
      if (body.verification_qr_image_base64) state.login.verifyQr = body.verification_qr_image_base64;
      if (body.logged_in) {
        window.clearInterval(qrTimer);
        await refreshAuth();
        state.login.hint = "登录成功。";
      }
      render();
    } catch (err) {
      state.login.error = err.message;
      render();
    }
  }, 2000);
}

async function openBrowserVerify() {
  if (!state.login.sessionId) return;
  try {
    const body = await api(`/auth/qr/browser?session_id=${encodeURIComponent(state.login.sessionId)}`, {
      method: "POST",
    });
    state.login.hint = body.hint || "已打开本机浏览器，请在里面完成验证。";
  } catch (err) {
    state.login.error = err.message;
  }
  render();
}

async function cookieLogin(event) {
  event.preventDefault();
  try {
    await api("/auth/cookie", {
      method: "POST",
      body: JSON.stringify({ cookie: state.login.cookie }),
    });
    state.login.cookie = "";
    await refreshAuth();
    state.login.hint = "Cookie 已导入。";
    state.login.error = "";
  } catch (err) {
    state.login.error = err.message;
  }
  render();
}

async function logout() {
  await api("/auth/logout", { method: "POST" });
  await refreshAuth();
  render();
}

function productCard(item) {
  const img = item.image_url
    ? `<img src="${escapeHtml(item.image_url)}" alt="" />`
    : `<div class="thumb"></div>`;
  const badge = item.is_new ? `<span class="badge">新</span>` : "";
  return `
    <article class="panel card">
      ${img}
      <div class="card-body">
        <h3>${escapeHtml(item.title || "未命名")}${badge}</h3>
        <p class="price">${escapeHtml(item.price || "价格未知")}</p>
        <div class="meta">
          <span>${escapeHtml(item.area || "地区未知")}</span>
          <span>${escapeHtml(item.seller || "匿名卖家")}</span>
          <span>${escapeHtml(item.publish_time || "")}</span>
        </div>
        ${item.link ? `<p><a href="${escapeHtml(item.link)}" target="_blank" rel="noopener">打开闲鱼</a></p>` : ""}
      </div>
    </article>
  `;
}

function renderProducts(items, emptyText) {
  if (!items.length) return `<p class="empty">${escapeHtml(emptyText)}</p>`;
  return `<div class="grid">${items.map(productCard).join("")}</div>`;
}

function renderSearch() {
  const s = state.search;
  const stats = s.stats
    ? `共 ${s.stats.total_results} 条，新增 ${s.stats.new_records} 条。`
    : "还没有搜过。";
  return `
    <form class="panel filters" id="search-form">
      <label>关键词<input name="keyword" required value="${escapeHtml(s.keyword)}" placeholder="索尼微单" /></label>
      <label>页数<input name="max_pages" type="number" min="1" max="20" value="${escapeHtml(s.max_pages)}" /></label>
      <label>排序
        <select name="sort">
          <option value="newest" ${s.sort === "newest" ? "selected" : ""}>最新发布</option>
          <option value="price_asc" ${s.sort === "price_asc" ? "selected" : ""}>价格从低到高</option>
          <option value="price_desc" ${s.sort === "price_desc" ? "selected" : ""}>价格从高到低</option>
          <option value="default" ${s.sort === "default" ? "selected" : ""}>综合</option>
        </select>
      </label>
      <label>最低价<input name="min_price" type="number" min="0" value="${escapeHtml(s.min_price)}" /></label>
      <label>最高价<input name="max_price" type="number" min="0" value="${escapeHtml(s.max_price)}" /></label>
      <label>城市<input name="city" value="${escapeHtml(s.city)}" placeholder="深圳" /></label>
      <label>最近天数<input name="publish_days" type="number" min="1" max="180" value="${escapeHtml(s.publish_days)}" /></label>
      <button class="btn" ${s.busy ? "disabled" : ""}>${s.busy ? "在搜…" : "搜索"}</button>
    </form>
    <p class="note">${escapeHtml(stats)}</p>
    ${s.error ? `<p class="error">${escapeHtml(s.error)}</p>` : ""}
    ${renderProducts(s.items, "输入关键词后，卡片会排在这里。")}
  `;
}

function renderShelf() {
  return `
    <form class="panel row" id="shelf-form">
      <label style="flex:1">货架标题<input name="q" value="${escapeHtml(state.shelf.q)}" placeholder="相机" /></label>
      <button class="btn">筛选</button>
    </form>
    <p class="note">货架共 ${state.shelf.total} 件。</p>
    ${state.shelf.error ? `<p class="error">${escapeHtml(state.shelf.error)}</p>` : ""}
    ${renderProducts(state.shelf.items, "货架还是空的。先去搜一批。")}
  `;
}

function renderInbox() {
  const convs = state.inbox.conversations
    .map((item) => {
      const active = item.conversation_id === state.inbox.active ? "active" : "";
      return `
        <button class="conv ${active}" data-open-conv="${escapeHtml(item.conversation_id)}">
          <b>${escapeHtml(item.sender_name || item.conversation_id)}</b>
          <span>${escapeHtml(item.text || "")}</span>
        </button>
      `;
    })
    .join("");
  const messages = state.inbox.messages
    .map((item) => {
      const cls = item.direction === "out" ? "out" : "in";
      return `<div class="bubble ${cls}">${escapeHtml(item.text)}</div>`;
    })
    .join("");
  return `
    <div class="panel inbox">
      <section class="conv-list">
        <div class="conv-head">
          <strong>会话</strong>
          ${state.im.connected
            ? `<button class="btn ghost" data-action="im-stop">断开</button>`
            : `<button class="btn" data-action="im-start">连接</button>`}
        </div>
        ${convs || `<p class="empty" style="padding:16px">连上之后，这里会出现会话。</p>`}
      </section>
      <section class="thread">
        <div class="thread-head">
          <strong>${escapeHtml(state.inbox.active || "选一个会话")}</strong>
          <span class="chip ${state.im.connected ? "ok" : "warn"}">${state.im.connected ? "在线" : "未连接"}</span>
        </div>
        <div class="messages">${messages || `<p class="empty">还没有消息。</p>`}</div>
        <form class="composer" id="send-form">
          <input name="text" value="${escapeHtml(state.inbox.draft)}" placeholder="说一句…" ${state.inbox.active ? "" : "disabled"} />
          <button class="btn" ${state.inbox.active ? "" : "disabled"}>发送</button>
        </form>
      </section>
    </div>
    ${state.inbox.notice ? `<p class="note">${escapeHtml(state.inbox.notice)}</p>` : ""}
    ${state.inbox.error ? `<p class="error">${escapeHtml(state.inbox.error)}</p>` : ""}
  `;
}

function renderLogin() {
  const qr = state.login.verifyQr || state.login.qr;
  return `
    <div class="login-grid">
      <section class="panel stack">
        <div class="qr-box">
          ${qr ? `<img alt="登录二维码" src="data:image/png;base64,${qr}" />` : `<p>点下面生成登录码。</p>`}
        </div>
        <div class="row">
          <button class="btn" data-action="qr-start" ${state.login.busy ? "disabled" : ""}>生成登录码</button>
          <button class="btn ghost" data-action="qr-browser" ${state.login.sessionId ? "" : "disabled"}>打开浏览器验证</button>
          <button class="btn ghost" data-action="logout" ${state.auth.logged_in ? "" : "disabled"}>退出</button>
        </div>
        <p class="note">${escapeHtml(state.login.hint || "用闲鱼 App 扫码，不要用系统相机。")}</p>
      </section>
      <form class="panel stack" id="cookie-form">
        <label>粘贴 www.goofish.com 的完整 Cookie
          <textarea name="cookie" placeholder="unb=...; cookie2=...; _m_h5_tk=...">${escapeHtml(state.login.cookie)}</textarea>
        </label>
        <button class="btn stamp">导入 Cookie</button>
        <p class="note">适合已经在浏览器里登录过的情况。</p>
      </form>
    </div>
    ${state.login.error ? `<p class="error">${escapeHtml(state.login.error)}</p>` : ""}
  `;
}

function authChip() {
  if (state.auth.logged_in) return `<span class="chip ok">已登录 ${escapeHtml(state.auth.user_id || "")}</span>`;
  if (state.auth.login_expired) return `<span class="chip bad">登录失效</span>`;
  return `<span class="chip">未登录</span>`;
}

function render() {
  const meta = views[state.view];
  const body = {
    search: renderSearch,
    shelf: renderShelf,
    inbox: renderInbox,
    login: renderLogin,
  }[state.view]();
  document.getElementById("app").innerHTML = `
    <div class="shell">
      <aside class="rail">
        <div class="brand">
          <div class="brand-mark">鱼</div>
          <strong>闲鱼工作台</strong>
          <span>本机客户端</span>
        </div>
        <nav class="nav">
          <button data-view="search" class="${state.view === "search" ? "active" : ""}">搜货<small>关键词、价格、城市</small></button>
          <button data-view="shelf" class="${state.view === "shelf" ? "active" : ""}">货架<small>已经存下来的商品</small></button>
          <button data-view="inbox" class="${state.view === "inbox" ? "active" : ""}">私信<small>收发闲鱼文本</small></button>
          <button data-view="login" class="${state.view === "login" ? "active" : ""}">登录<small>扫码或 Cookie</small></button>
        </nav>
      </aside>
      <main class="main">
        <header class="topbar">
          <div>
            <h1>${meta.title}</h1>
            <p class="lede">${meta.lede}</p>
          </div>
          <div class="chips">
            ${authChip()}
            <span class="chip ${state.im.connected ? "ok" : ""}">IM ${state.im.connected ? "在线" : "未连接"}</span>
          </div>
        </header>
        ${body}
      </main>
    </div>
  `;
}

function bind() {
  document.addEventListener("click", (event) => {
    const viewBtn = event.target.closest("[data-view]");
    if (viewBtn) {
      setView(viewBtn.dataset.view);
      return;
    }
    const action = event.target.closest("[data-action]");
    if (action) {
      const name = action.dataset.action;
      if (name === "im-start") startIm();
      if (name === "im-stop") stopIm();
      if (name === "qr-start") startQr();
      if (name === "qr-browser") openBrowserVerify();
      if (name === "logout") logout();
      return;
    }
    const conv = event.target.closest("[data-open-conv]");
    if (conv) openConversation(conv.dataset.openConv);
  });
  document.addEventListener("submit", (event) => {
    if (event.target.id === "search-form") runSearch(event);
    if (event.target.id === "shelf-form") {
      event.preventDefault();
      state.shelf.q = String(new FormData(event.target).get("q") || "").trim();
      loadShelf();
    }
    if (event.target.id === "send-form") {
      state.inbox.draft = String(new FormData(event.target).get("text") || "");
      sendMessage(event);
    }
    if (event.target.id === "cookie-form") {
      state.login.cookie = String(new FormData(event.target).get("cookie") || "");
      cookieLogin(event);
    }
  });
  document.addEventListener("input", (event) => {
    if (event.target.closest("#send-form") && event.target.name === "text") {
      state.inbox.draft = event.target.value;
    }
    if (event.target.closest("#cookie-form") && event.target.name === "cookie") {
      state.login.cookie = event.target.value;
    }
  });
}

async function boot() {
  const hash = location.hash.replace("#", "");
  state.view = views[hash] ? hash : "search";
  bind();
  try {
    await refreshAuth();
    await refreshIm();
    if (state.im.connected) listenIm();
  } catch {
    /* 后端还没起来时也先画出壳 */
  }
  if (state.view === "shelf") await loadShelf();
  render();
}

window.addEventListener("hashchange", () => {
  const hash = location.hash.replace("#", "");
  if (views[hash]) setView(hash);
});

boot();
