<template>
  <div class="split">
    <form class="panel stack" @submit.prevent="create">
      <label>名称<input v-model="form.name" placeholder="深圳相机盯盘" /></label>
      <label>关键词<input v-model="form.keyword" required placeholder="富士 xt30" /></label>
      <label>城市<input v-model="form.city" placeholder="深圳" /></label>
      <label>目标价<input v-model="form.target_price" type="number" min="0" placeholder="1200" /></label>
      <label>间隔（分钟）<input v-model.number="form.interval_minutes" type="number" min="1" /></label>
      <label>低于中位 %<input v-model="form.notify_below_median_pct" type="number" min="0" max="90" placeholder="20" /></label>
      <label class="row"><input v-model="form.notify_new" type="checkbox" /> 上新通知</label>
      <label class="row"><input v-model="form.notify_below_target" type="checkbox" /> 目标价通知</label>
      <button class="btn">创建盯盘</button>
      <p class="note">调度在引擎进程内运行；关掉服务任务会停。</p>
    </form>
    <section class="panel stack">
      <div class="row" style="justify-content: space-between">
        <strong>任务列表</strong>
        <span class="chip" :class="scheduler.running ? 'ok' : ''">调度 {{ scheduler.running ? "运行中" : "未启动" }}</span>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <table class="table" v-if="items.length">
        <thead>
          <tr><th>任务</th><th>间隔</th><th>上次</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>
              <b>{{ item.name || item.keyword }}</b>
              <div class="meta">{{ item.keyword }} · {{ item.city || "全国" }} · 目标 {{ item.target_price ?? "-" }}</div>
              <div v-if="item.last_error" class="error">{{ item.last_error }}</div>
            </td>
            <td>{{ item.interval_minutes }} 分</td>
            <td>{{ item.last_run_at || "尚未运行" }}</td>
            <td class="row">
              <button class="btn ghost" @click="run(item.id)">跑一次</button>
              <button class="btn ghost" @click="toggle(item)">{{ item.enabled ? "停用" : "启用" }}</button>
              <button class="btn ghost" @click="remove(item.id)">删</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">还没有盯盘任务。</p>
      <pre v-if="lastRun" class="note" style="white-space: pre-wrap">{{ lastRun }}</pre>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { api } from "../api";

const form = reactive({
  name: "",
  keyword: "",
  city: "",
  target_price: "",
  interval_minutes: 15,
  notify_new: true,
  notify_below_target: true,
  notify_below_median_pct: "",
});
const items = ref([]);
const scheduler = reactive({ running: false });
const error = ref("");
const lastRun = ref("");

async function load() {
  const body = await api("/watches");
  items.value = body.items || [];
  Object.assign(scheduler, body.scheduler || {});
}

async function create() {
  error.value = "";
  try {
    const payload = {
      name: form.name,
      keyword: form.keyword,
      city: form.city || null,
      interval_minutes: form.interval_minutes,
      notify_new: form.notify_new,
      notify_below_target: form.notify_below_target,
      target_price: form.target_price === "" ? null : Number(form.target_price),
      notify_below_median_pct:
        form.notify_below_median_pct === "" ? null : Number(form.notify_below_median_pct),
    };
    await api("/watches", { method: "POST", body: JSON.stringify(payload) });
    form.keyword = "";
    await load();
  } catch (err) {
    error.value = err.message;
  }
}

async function run(id) {
  try {
    const body = await api(`/watches/${id}/run`, { method: "POST" });
    lastRun.value = `跑完：共 ${body.total_results}，新增 ${body.new_records}，触发 ${body.triggered?.length || 0} 条`;
    await load();
  } catch (err) {
    error.value = err.message;
  }
}

async function toggle(item) {
  await api(`/watches/${item.id}`, {
    method: "PUT",
    body: JSON.stringify({ ...item, enabled: !item.enabled }),
  });
  await load();
}

async function remove(id) {
  await api(`/watches/${id}`, { method: "DELETE" });
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
