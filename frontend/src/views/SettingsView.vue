<template>
  <form class="panel stack" style="max-width: 640px" @submit.prevent="save">
    <label>自动回复
      <select v-model="form.autoreply_mode">
        <option value="off">关闭</option>
        <option value="draft">草稿（本期只支持草稿，不会实发）</option>
      </select>
    </label>
    <label>AI 厂商
      <select v-model="form.ai_provider" @change="applyPreset">
        <option value="auto">自动识别 Base URL</option>
        <option v-for="item in providers" :key="item.id" :value="item.id">{{ item.label }}</option>
      </select>
    </label>
    <label>AI Base URL
      <input v-model="form.ai_base_url" :placeholder="preset.base_url || 'https://api.deepseek.com/v1'" />
    </label>
    <label>AI Model
      <input v-model="form.ai_model" :placeholder="preset.model || 'deepseek-chat'" />
    </label>
    <label>AI API Key
      <input
        v-model="form.ai_api_key"
        type="password"
        :placeholder="keyPlaceholder"
      />
    </label>
    <p class="note">
      已识别：{{ resolvedLabel || "未配置" }}。
      OpenAI / DeepSeek / Groq / Gemini / 通义 / Kimi / 智谱 / OpenRouter / 硅基流动 / Together / MiniMax / 零一万物 走兼容接口；
      Claude 走 Anthropic；Azure 填资源域名和部署名；Ollama 本地默认不用 Key。
    </p>
    <button class="btn">保存</button>
    <p class="note">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "../api";

const form = reactive({
  autoreply_mode: "off",
  ai_provider: "auto",
  ai_base_url: "",
  ai_model: "deepseek-chat",
  ai_api_key: "",
});
const providers = ref([]);
const hasKey = ref(false);
const needsKey = ref(true);
const resolvedLabel = ref("");
const message = ref("");
const error = ref("");

const preset = computed(() => providers.value.find((item) => item.id === form.ai_provider) || {});
const keyPlaceholder = computed(() => {
  if (!needsKey.value) return "Ollama 等本地服务可留空";
  return hasKey.value ? "已配置，留空不修改" : "sk-... / API Key";
});

function applyPreset() {
  const item = preset.value;
  if (!item || form.ai_provider === "auto" || form.ai_provider === "custom") return;
  if (item.base_url) form.ai_base_url = item.base_url;
  if (item.model) form.ai_model = item.model;
  needsKey.value = item.needs_key !== false;
}

async function load() {
  const [body, catalog] = await Promise.all([api("/settings"), api("/ai/providers")]);
  providers.value = catalog.items || [];
  form.autoreply_mode = body.autoreply_mode === "send" ? "draft" : body.autoreply_mode || "off";
  form.ai_provider = body.ai_provider || "auto";
  form.ai_base_url = body.ai_base_url || "";
  form.ai_model = body.ai_model || "deepseek-chat";
  hasKey.value = !!body.has_ai_api_key;
  needsKey.value = body.needs_key !== false;
  resolvedLabel.value = body.resolved_label || "";
}

async function save() {
  try {
    const payload = {
      autoreply_mode: form.autoreply_mode,
      ai_provider: form.ai_provider,
      ai_base_url: form.ai_base_url,
      ai_model: form.ai_model,
    };
    if (form.ai_api_key.trim()) payload.ai_api_key = form.ai_api_key.trim();
    const body = await api("/settings", { method: "PUT", body: JSON.stringify(payload) });
    form.ai_api_key = "";
    message.value = body.hint || "已保存。";
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
