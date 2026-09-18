<template>
  <div class="shell">
    <aside class="rail">
      <div class="brand">
        <div class="brand-mark">鱼</div>
        <div>
          <strong>闲鱼工作台</strong>
          <span>本机引擎</span>
        </div>
      </div>
      <nav class="nav">
        <RouterLink v-for="item in nav" :key="item.to" :to="item.to">
          {{ item.label }}
          <small>{{ item.hint }}</small>
        </RouterLink>
      </nav>
    </aside>
    <main class="main">
      <header class="topbar">
        <div>
          <h1>{{ title }}</h1>
          <p class="lede">{{ lede }}</p>
        </div>
        <div class="chips">
          <span class="chip" :class="auth.logged_in ? 'ok' : auth.login_expired ? 'bad' : ''">
            {{ auth.logged_in ? `已登录 ${auth.user_id || ""}` : auth.login_expired ? "登录失效" : "未登录" }}
          </span>
          <span class="chip" :class="im.connected ? 'ok' : ''">IM {{ im.connected ? "在线" : "未连接" }}</span>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive } from "vue";
import { useRoute } from "vue-router";
import { api } from "./api";

const route = useRoute();
const auth = reactive({ logged_in: false, user_id: "", login_expired: false });
const im = reactive({ connected: false, running: false });

const nav = [
  { to: "/search", label: "搜货", hint: "关键词与筛选" },
  { to: "/shelf", label: "货架", hint: "本机库存" },
  { to: "/watches", label: "盯盘", hint: "定时与低价" },
  { to: "/ai", label: "AI", hint: "问询与判断" },
  { to: "/inbox", label: "私信", hint: "收发文本" },
  { to: "/autoreply", label: "自动回复", hint: "规则与草稿" },
  { to: "/notify", label: "通知", hint: "Bark 等推送" },
  { to: "/login", label: "登录", hint: "扫码 / Cookie" },
  { to: "/settings", label: "设置", hint: "模型与模式" },
];

const title = computed(() => route.meta.title || "闲鱼工作台");
const lede = computed(() => route.meta.lede || "");

async function refresh() {
  try {
    Object.assign(auth, await api("/auth/status"));
  } catch {}
  try {
    Object.assign(im, await api("/im/status"));
  } catch {}
}

onMounted(() => {
  refresh();
  window.setInterval(refresh, 30000);
});
defineExpose({ refresh });
</script>
