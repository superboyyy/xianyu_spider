<template>
  <form class="panel row" @submit.prevent="load">
    <label style="flex: 1">货架标题<input v-model="q" placeholder="相机" /></label>
    <button class="btn">筛选</button>
    <button class="btn ghost" type="button" @click="loadStats">看均价</button>
  </form>
  <p class="note">货架共 {{ total }} 件。{{ statsLine }}</p>
  <p v-if="error" class="error">{{ error }}</p>
  <div v-if="items.length" class="grid">
    <ProductCard v-for="item in items" :key="item.id" :item="item" />
  </div>
  <p v-else class="empty">货架还是空的。先去搜一批。</p>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "../api";
import ProductCard from "../components/ProductCard.vue";

const q = ref("");
const items = ref([]);
const total = ref(0);
const stats = ref(null);
const error = ref("");

const statsLine = computed(() => {
  if (!stats.value || !stats.value.sample_n) return "";
  return `样本 ${stats.value.sample_n}：中位 ${stats.value.median}，均值 ${stats.value.mean}。`;
});

async function load() {
  try {
    const query = q.value.trim() ? `?q=${encodeURIComponent(q.value.trim())}` : "";
    const body = await api(`/products${query}`);
    items.value = body.items || [];
    total.value = body.total || 0;
    error.value = "";
  } catch (err) {
    error.value = err.message;
  }
}

async function loadStats() {
  if (!q.value.trim()) {
    error.value = "先填关键词再看均价。";
    return;
  }
  try {
    stats.value = await api(`/products/stats?q=${encodeURIComponent(q.value.trim())}`);
    error.value = "";
  } catch (err) {
    error.value = err.message;
  }
}

onMounted(load);
</script>
