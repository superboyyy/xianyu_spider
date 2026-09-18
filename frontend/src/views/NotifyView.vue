<template>
  <div class="split">
    <form class="panel stack" @submit.prevent="create">
      <label>名称<input v-model="form.name" placeholder="我的 Bark" /></label>
      <label>类型
        <select v-model="form.kind">
          <option value="bark">Bark</option>
          <option value="webhook">Webhook</option>
        </select>
      </label>
      <label>Endpoint / Key
        <textarea v-model="form.endpoint" required placeholder="Bark key，或 https://api.day.app/xxx" />
      </label>
      <div class="row">
        <button class="btn">保存渠道</button>
        <button class="btn ghost" type="button" @click="test">测试推送</button>
      </div>
      <p class="note">Bark 可填 key，或完整 `https://api.day.app/{key}`。</p>
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
import { onMounted, reactive, ref } from "vue";
import { api } from "../api";

const form = reactive({ name: "Bark", kind: "bark", endpoint: "" });
const channels = ref([]);
const events = ref([]);
const error = ref("");

async function load() {
  channels.value = (await api("/notify/channels")).items || [];
  events.value = (await api("/notify/events")).items || [];
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
