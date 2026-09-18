<template>
  <div class="panel inbox">
    <section class="conv-list">
      <div class="conv-head">
        <strong>会话</strong>
        <button v-if="im.connected" class="btn ghost" @click="stopIm">断开</button>
        <button v-else class="btn" @click="startIm">连接</button>
      </div>
      <button
        v-for="item in conversations"
        :key="item.conversation_id"
        class="conv"
        :class="{ active: item.conversation_id === active }"
        @click="open(item.conversation_id)"
      >
        <b>{{ item.sender_name || item.conversation_id }}</b>
        <span>{{ item.text }}</span>
      </button>
      <p v-if="!conversations.length" class="empty" style="padding: 16px">连上之后，这里会出现会话。</p>
    </section>
    <section class="thread">
      <div class="thread-head">
        <strong>{{ active || "选一个会话" }}</strong>
        <span class="chip" :class="im.connected ? 'ok' : 'warn'">{{ im.connected ? "在线" : "未连接" }}</span>
      </div>
      <div class="messages">
        <div v-for="item in messages" :key="item.id" class="bubble" :class="item.direction === 'out' ? 'out' : ''">
          {{ item.text }}
        </div>
        <p v-if="!messages.length" class="empty">还没有消息。</p>
      </div>
      <form class="composer" @submit.prevent="send">
        <input v-model="text" :disabled="!active" placeholder="说一句…" />
        <button class="btn" :disabled="!active">发送</button>
      </form>
    </section>
  </div>
  <p v-if="notice" class="note">{{ notice }}</p>
  <p v-if="error" class="error">{{ error }}</p>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from "vue";
import { api } from "../api";

const im = reactive({ connected: false, running: false });
const conversations = ref([]);
const messages = ref([]);
const active = ref("");
const text = ref("");
const error = ref("");
const notice = ref("");
let events = null;

async function refreshStatus() {
  Object.assign(im, await api("/im/status"));
}

async function loadConversations() {
  conversations.value = await api("/im/conversations");
}

async function open(id) {
  active.value = id;
  messages.value = await api(`/im/messages?conversation_id=${encodeURIComponent(id)}`);
}

function listen() {
  if (events) events.close();
  events = new EventSource("/im/events");
  events.onmessage = async (event) => {
    try {
      const item = JSON.parse(event.data);
      if (item.event === "connected") return;
      if (item.event === "autoreply") {
        notice.value = `草稿：${item.reply || ""}（不会自动发送）`;
        return;
      }
      await loadConversations();
      if (item.conversation_id && item.conversation_id === active.value) await open(active.value);
    } catch {}
  };
}

async function startIm() {
  try {
    await api("/im/start", { method: "POST" });
    listen();
    notice.value = "IM 已连接。不要和网页版同时开。自动回复只会出草稿。";
    await refreshStatus();
    await loadConversations();
    error.value = "";
  } catch (err) {
    error.value = err.message;
  }
}

async function stopIm() {
  await api("/im/stop", { method: "POST" });
  if (events) events.close();
  events = null;
  await refreshStatus();
}

async function send() {
  if (!active.value || !text.value.trim()) return;
  try {
    await api("/im/send", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: active.value,
        to_user_id: active.value,
        text: text.value,
        source: "user",
      }),
    });
    text.value = "";
    await open(active.value);
  } catch (err) {
    error.value = err.message;
  }
}

onMounted(async () => {
  try {
    await refreshStatus();
    await loadConversations();
    if (im.connected) listen();
  } catch (err) {
    error.value = err.message;
  }
});

onUnmounted(() => {
  if (events) events.close();
});
</script>
