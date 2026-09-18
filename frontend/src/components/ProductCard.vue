<template>
  <article class="panel card">
    <img v-if="item.image_url" :src="item.image_url" alt="" />
    <div v-else class="thumb" />
    <div class="card-body">
      <h3>
        {{ item.title || "未命名" }}
        <span v-if="item.is_new" class="badge">新</span>
      </h3>
      <p class="price">{{ item.price || "价格未知" }}</p>
      <div class="meta">
        <span>{{ item.area || "地区未知" }}</span>
        <span>{{ item.seller || "匿名卖家" }}</span>
        <span>{{ item.publish_time || "" }}</span>
      </div>
      <p class="row" style="margin: 10px 0 0">
        <a v-if="item.link" :href="item.link" target="_blank" rel="noopener">打开闲鱼</a>
        <RouterLink v-if="ask && item.title" :to="{ path: '/ai', query: { q: askText } }">问 AI</RouterLink>
        <RouterLink v-if="watch && item.title" :to="{ path: '/watches', query: { keyword: item.title, target: priceHint } }">盯盘</RouterLink>
      </p>
    </div>
  </article>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  item: { type: Object, required: true },
  ask: { type: Boolean, default: false },
  watch: { type: Boolean, default: false },
});

const askText = computed(
  () => `这个「${props.item.title}」值不值入手？标价 ${props.item.price || "未知"}`
);
const priceHint = computed(() => String(props.item.price || "").replace(/[^\d.]/g, ""));
</script>
