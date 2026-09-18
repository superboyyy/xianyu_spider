import { createRouter, createWebHashHistory } from "vue-router";
import SearchView from "./views/SearchView.vue";
import ShelfView from "./views/ShelfView.vue";
import WatchView from "./views/WatchView.vue";
import AiView from "./views/AiView.vue";
import InboxView from "./views/InboxView.vue";
import AutoreplyView from "./views/AutoreplyView.vue";
import NotifyView from "./views/NotifyView.vue";
import LoginView from "./views/LoginView.vue";
import SettingsView from "./views/SettingsView.vue";

const routes = [
  { path: "/", redirect: "/search" },
  { path: "/search", component: SearchView, meta: { title: "搜货", lede: "按关键词、价格和地区抓取闲鱼。" } },
  { path: "/shelf", component: ShelfView, meta: { title: "货架", lede: "已经落库的商品，断网也能翻。" } },
  { path: "/watches", component: WatchView, meta: { title: "盯盘", lede: "定时搜索，低价与上新推到 Bark。" } },
  { path: "/ai", component: AiView, meta: { title: "AI", lede: "找货、均价、入手判断与起草私信。" } },
  { path: "/inbox", component: InboxView, meta: { title: "私信", lede: "登录后连接闲鱼 IM，不要和网页版同时开。" } },
  { path: "/autoreply", component: AutoreplyView, meta: { title: "自动回复", lede: "规则优先；默认先出草稿。" } },
  { path: "/notify", component: NotifyView, meta: { title: "通知", lede: "Bark / Webhook 渠道与推送记录。" } },
  { path: "/login", component: LoginView, meta: { title: "登录", lede: "扫码、拍脸或粘贴 Cookie，只保存在本机。" } },
  { path: "/settings", component: SettingsView, meta: { title: "设置", lede: "AI Key、自动回复档位。" } },
];

export default createRouter({
  history: createWebHashHistory(),
  routes,
});
