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
      <p v-if="item.link" style="margin: 10px 0 0">
        <a :href="item.link" target="_blank" rel="noopener">打开闲鱼</a>
      </p>
    </div>
  </article>
</template>

<script setup>
defineProps({ item: { type: Object, required: true } });
</script>
