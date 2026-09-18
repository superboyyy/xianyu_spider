<template>
  <div class="split">
    <form class="panel stack" @submit.prevent="create">
      <label>名称<input v-model="form.name" :placeholder="current?.label || '我的渠道'" /></label>
      <label>类型
        <select v-model="form.kind">
          <option v-for="item in kinds" :key="item.id" :value="item.id">{{ item.label }}</option>
        </select>
      </label>
      <label>Endpoint / Key
        <textarea v-model="form.endpoint" required :placeholder="current?.placeholder || ''" />
      </label>
      <div class="row">
        <button class="btn">保存渠道</button>
        <button class="btn ghost" type="button" @click="test">测试推送</button>
      </div>
      <p class="note">{{ hint }}</p>
    </form>
    <section class="panel stack">
      <strong>已配置渠道</strong>
      <p v-if="error" class="error">{{ error }}</p>
      <table class="table" v-if="channels.length">
        <thead><tr><th>名称</th><th>类型</th><th>Endpoint</th><th></th></tr></thead>
        <tbody>
          <tr v-for="c in channels" :key="c.id">
            <td>{{ c.name }}</td>
            <td>{{ c.kind }}</td>
            <td>{{ c.endpoint_masked }}</td>
            <td><button class="btn ghost" @click="remove(c.id)">删</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">还没有通知渠道。</p>
      <strong>最近事件</strong>
      <table class="table" v-if="events.length">
        <thead><tr><th>类型</th><th>标题</th><th>结果</th></tr></thead>
        <tbody>
          <tr v-for="e in events" :key="e.id">
            <td>{{ e.event_type }}</td>
            <td>{{ e.title }}<div class="meta">{{ e.body }}</div></td>
            <td>{{ e.ok ? "成功" : e.error || "失败" }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "../api";

const kinds = ref([
  { id: "bark", label: "Bark", placeholder: "key 或 https://api.day.app/{key}" },
  { id: "webhook", label: "通用 Webhook", placeholder: "https://example.com/hook" },
]);
const form = reactive({ name: "Bark", kind: "bark", endpoint: "" });
const channels = ref([]);
const events = ref([]);
const error = ref("");

const current = computed(() => kinds.value.find((item) => item.id === form.kind));
const hint = computed(() => {
  const map = {
    bark: "Bark 可填 key，或完整 https://api.day.app/{key}。",
    webhook: "任意 POST JSON：{title, body, payload}。",
    ntfy: "填 https://ntfy.sh/主题，或 `token 主题`。",
    telegram: "填 bot_token|chat_id。",
    serverchan: "填 Server酱 SendKey。",
    wecom: "填企业微信机器人 key，或完整 webhook URL。",
  };
  return map[form.kind] || "";
});

async function load() {
  const [kindBody, channelBody, eventBody] = await Promise.all([
    api("/notify/kinds").catch(() => ({ items: kinds.value })),
    api("/notify/channels"),
    api("/notify/events"),
  ]);
  if (kindBody.items?.length) kinds.value = kindBody.items;
  channels.value = channelBody.items || [];
  events.value = eventBody.items || [];
}

async function create() {
  try {
    await api("/notify/channels", { method: "POST", body: JSON.stringify(form) });
    form.endpoint = "";
    await load();
  } catch (err) {
    error.value = err.message;
  }
}

async function remove(id) {
  await api(`/notify/channels/${id}`, { method: "DELETE" });
  await load();
}

async function test() {
  try {
    await api("/notify/test", {
      method: "POST",
      body: JSON.stringify({ title: "闲鱼工作台", body: "测试推送成功" }),
    });
    await load();
  } catch (err) {
    error.value = err.message;
  }
}

onMounted(async () => {
  try {
    await load();
  } catch (err) {
    error.value = err.message;
  }
});
</script>
