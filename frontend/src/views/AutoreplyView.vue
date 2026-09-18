<template>
  <div class="split">
    <form class="panel stack" @submit.prevent="create">
      <label>名称<input v-model="form.name" placeholder="还在吗" /></label>
      <label>匹配关键词<input v-model="form.match_text" required placeholder="还在" /></label>
      <label>回复内容<textarea v-model="form.reply_text" required placeholder="在的，可小刀" /></label>
      <label>冷却秒数<input v-model.number="form.cooldown_seconds" type="number" min="0" /></label>
      <label class="row"><input v-model="form.only_first" type="checkbox" /> 每个会话只回一次</label>
      <button class="btn">添加规则</button>
      <p class="note">全局模式在设置里：关闭 / 草稿 / 实发。默认建议草稿。</p>
    </form>
    <section class="panel stack">
      <strong>规则</strong>
      <p v-if="error" class="error">{{ error }}</p>
      <table class="table" v-if="rules.length">
        <thead><tr><th>规则</th><th>匹配</th><th></th></tr></thead>
        <tbody>
          <tr v-for="rule in rules" :key="rule.id">
            <td>{{ rule.name || rule.id }}</td>
            <td>{{ rule.match_text }} → {{ rule.reply_text }}</td>
            <td><button class="btn ghost" @click="remove(rule.id)">删</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">还没有规则。</p>
      <strong>最近日志</strong>
      <table class="table" v-if="logs.length">
        <thead><tr><th>会话</th><th>状态</th><th>回复</th></tr></thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td>{{ log.conversation_id }}</td>
            <td>{{ log.status }}</td>
            <td>{{ log.reply }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { api } from "../api";

const form = reactive({
  name: "",
  match_text: "",
  reply_text: "",
  cooldown_seconds: 300,
  only_first: false,
});
const rules = ref([]);
const logs = ref([]);
const error = ref("");

async function load() {
  rules.value = (await api("/autoreply/rules")).items || [];
  logs.value = (await api("/autoreply/logs")).items || [];
}

async function create() {
  try {
    await api("/autoreply/rules", { method: "POST", body: JSON.stringify(form) });
    form.match_text = "";
    form.reply_text = "";
    await load();
  } catch (err) {
    error.value = err.message;
  }
}

async function remove(id) {
  await api(`/autoreply/rules/${id}`, { method: "DELETE" });
  await load();
}

onMounted(async () => {
  try {
    await load();
  } catch (err) {
    error.value = err.message;
  }
});
</script>
