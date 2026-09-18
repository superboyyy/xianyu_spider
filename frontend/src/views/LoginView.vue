<template>
  <div class="login-grid">
    <section class="panel stack">
      <div class="qr-box">
        <img v-if="qr" :src="`data:image/png;base64,${qr}`" alt="登录二维码" />
        <p v-else>点下面生成登录码。</p>
      </div>
      <div class="row">
        <button class="btn" :disabled="busy" @click="startQr">生成登录码</button>
        <button class="btn ghost" :disabled="!sessionId" @click="openBrowser">打开浏览器验证</button>
        <button class="btn ghost" @click="logout">退出</button>
      </div>
      <p class="note">{{ hint || "用闲鱼 App 扫码，不要用系统相机。" }}</p>
    </section>
    <form class="panel stack" @submit.prevent="cookieLogin">
      <label>粘贴 www.goofish.com 的完整 Cookie
        <textarea v-model="cookie" placeholder="unb=...; cookie2=...; _m_h5_tk=..." />
      </label>
      <button class="btn">导入 Cookie</button>
      <p class="note">适合已经在浏览器里登录过的情况。</p>
    </form>
  </div>
  <p v-if="error" class="error">{{ error }}</p>
</template>

<script setup>
import { onUnmounted, ref } from "vue";
import { api } from "../api";

const sessionId = ref("");
const qr = ref("");
const hint = ref("");
const cookie = ref("");
const busy = ref(false);
const error = ref("");
let timer = 0;

async function startQr() {
  busy.value = true;
  error.value = "";
  try {
    const body = await api("/auth/qr/start", { method: "POST" });
    sessionId.value = body.session_id || "";
    qr.value = body.qr_image_base64 || "";
    hint.value = body.hint || body.message || "";
    poll();
  } catch (err) {
    error.value = err.message;
  } finally {
    busy.value = false;
  }
}

function poll() {
  window.clearInterval(timer);
  if (!sessionId.value) return;
  timer = window.setInterval(async () => {
    try {
      const body = await api(`/auth/qr/status?session_id=${encodeURIComponent(sessionId.value)}`);
      hint.value = body.hint || "";
      if (body.verification_qr_image_base64) qr.value = body.verification_qr_image_base64;
      if (body.logged_in) {
        window.clearInterval(timer);
        hint.value = "登录成功。";
      }
    } catch (err) {
      error.value = err.message;
    }
  }, 2000);
}

async function openBrowser() {
  if (!sessionId.value) return;
  try {
    const body = await api(`/auth/qr/browser?session_id=${encodeURIComponent(sessionId.value)}`, {
      method: "POST",
    });
    hint.value = body.hint || "已打开本机浏览器。";
  } catch (err) {
    error.value = err.message;
  }
}

async function cookieLogin() {
  try {
    await api("/auth/cookie", { method: "POST", body: JSON.stringify({ cookie: cookie.value }) });
    cookie.value = "";
    hint.value = "Cookie 已导入。";
  } catch (err) {
    error.value = err.message;
  }
}

async function logout() {
  await api("/auth/logout", { method: "POST" });
  hint.value = "已退出。";
}

onUnmounted(() => window.clearInterval(timer));
</script>
