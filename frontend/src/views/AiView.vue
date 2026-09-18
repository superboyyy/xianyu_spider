<template>
  <div class="split">
    <section class="panel stack">
      <div class="messages" style="min-height: 360px">
        <div v-for="(m, idx) in messages" :key="idx" class="bubble" :class="m.role === 'user' ? 'out' : ''">
          {{ m.content }}
        </div>
        <p v-if="!messages.length" class="empty">问问「深圳 2000 内富士 xt30 能入吗」。</p>
      </div>
      <form class="composer" @submit.prevent="send">
        <input v-model="draft" :disabled="busy" placeholder="用中文描述你的需求…" />
        <button class="btn" :disabled="busy || !draft.trim()">{{ busy ? "想…" : "发送" }}</button>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="offline" class="note">当前无 AI Key，已用本机样本做粗判。去设置里填 Key 可开完整对话。</p>
    </section>
    <section class="panel stack">
      <strong>引用商品</strong>
      <div v-if="refs.length" class="ai-refs">
        <ProductCard v-for="item in refs" :key="item.id || item.link" :item="item" />
      </div>
      <p v-else class="empty">工具返回的商品会显示在这里。</p>
    </section>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { api } from "../api";
import ProductCard from "../components/ProductCard.vue";

const draft = ref("");
const messages = ref([]);
const refs = ref([]);
const threadId = ref(null);
const busy = ref(false);
const error = ref("");
const offline = ref(false);

async function send() {
  const text = draft.value.trim();
  if (!text) return;
  messages.value.push({ role: "user", content: text });
  draft.value = "";
  busy.value = true;
  error.value = "";
  try {
    const body = await api("/ai/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, thread_id: threadId.value }),
    });
    threadId.value = body.thread_id;
    messages.value.push({ role: "assistant", content: body.reply });
    refs.value = body.refs || [];
    offline.value = !!body.offline;
  } catch (err) {
    error.value = err.message;
  } finally {
    busy.value = false;
  }
}
</script>
