<template>
  <form class="panel stack" style="max-width: 560px" @submit.prevent="save">
    <label>自动回复模式
      <select v-model="form.autoreply_mode">
        <option value="off">关闭</option>
        <option value="draft">草稿（推荐）</option>
        <option value="send">直接发送</option>
      </select>
    </label>
    <label>AI Base URL<input v-model="form.ai_base_url" placeholder="https://api.deepseek.com/v1" /></label>
    <label>AI Model<input v-model="form.ai_model" placeholder="deepseek-chat" /></label>
    <label>AI API Key
      <input v-model="form.ai_api_key" type="password" :placeholder="hasKey ? '已配置，留空不修改' : 'sk-...'" />
    </label>
    <button class="btn">保存</button>
    <p class="note">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { api } from "../api";

const form = reactive({
  autoreply_mode: "off",
  ai_base_url: "",
  ai_model: "deepseek-chat",
  ai_api_key: "",
});
const hasKey = ref(false);
const message = ref("");
const error = ref("");

async function load() {
  const body = await api("/settings");
  form.autoreply_mode = body.autoreply_mode || "off";
  form.ai_base_url = body.ai_base_url || "";
  form.ai_model = body.ai_model || "deepseek-chat";
  hasKey.value = !!body.has_ai_api_key;
}

async function save() {
  try {
    const payload = {
      autoreply_mode: form.autoreply_mode,
      ai_base_url: form.ai_base_url,
      ai_model: form.ai_model,
    };
    if (form.ai_api_key.trim()) payload.ai_api_key = form.ai_api_key.trim();
    await api("/settings", { method: "PUT", body: JSON.stringify(payload) });
    form.ai_api_key = "";
    message.value = "已保存。";
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
