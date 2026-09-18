<template>
  <form class="panel filters" @submit.prevent="runSearch">
    <label>关键词<input v-model="form.keyword" required placeholder="索尼微单" /></label>
    <label>页数<input v-model.number="form.max_pages" type="number" min="1" max="10" /></label>
    <label>排序
      <select v-model="form.sort">
        <option value="newest">最新发布</option>
        <option value="price_asc">价格升序</option>
        <option value="price_desc">价格降序</option>
        <option value="default">综合</option>
      </select>
    </label>
    <label>最低价<input v-model="form.min_price" type="number" min="0" /></label>
    <label>最高价<input v-model="form.max_price" type="number" min="0" /></label>
    <label>城市<input v-model="form.city" placeholder="深圳" /></label>
    <button class="btn" :disabled="busy">{{ busy ? "在搜…" : "搜索" }}</button>
  </form>
  <p v-if="loginExpired" class="error">登录已失效，这次按未登录继续搜。去登录页重新扫码即可。</p>
  <p class="note">{{ statsText }}</p>
  <p v-if="error" class="error">{{ error }}</p>
  <div v-if="items.length" class="grid">
    <ProductCard v-for="item in items" :key="item.id || item.link" :item="item" ask />
  </div>
  <p v-else class="empty">输入关键词后，卡片会排在这里。</p>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { api } from "../api";
import ProductCard from "../components/ProductCard.vue";

const form = reactive({
  keyword: "",
  max_pages: 1,
  sort: "newest",
  min_price: "",
  max_price: "",
  city: "",
});
const items = ref([]);
const stats = ref(null);
const busy = ref(false);
const error = ref("");
const loginExpired = ref(false);

const statsText = computed(() =>
  stats.value
    ? `共 ${stats.value.total_results} 条，新增 ${stats.value.new_records} 条。`
    : "还没有搜过。"
);

async function runSearch() {
  busy.value = true;
  error.value = "";
  loginExpired.value = false;
  try {
    const payload = {
      keyword: form.keyword.trim(),
      max_pages: form.max_pages || 1,
      sort: form.sort,
    };
    if (form.min_price !== "") payload.min_price = Number(form.min_price);
    if (form.max_price !== "") payload.max_price = Number(form.max_price);
    if (form.city.trim()) payload.city = form.city.trim();
    const body = await api("/search/", { method: "POST", body: JSON.stringify(payload) });
    items.value = body.items || [];
    stats.value = body;
    loginExpired.value = !!body.login_expired;
  } catch (err) {
    error.value = err.message;
  } finally {
    busy.value = false;
  }
}
</script>
