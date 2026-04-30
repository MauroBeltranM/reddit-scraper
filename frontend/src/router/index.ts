import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/", name: "dashboard", component: () => import("../views/DashboardView.vue") },
  { path: "/subreddits", name: "subreddits", component: () => import("../views/SubredditsView.vue") },
  { path: "/posts", name: "posts", component: () => import("../views/PostsView.vue") },
  { path: "/posts/:id", name: "post", component: () => import("../views/PostDetailView.vue") },
  { path: "/search", name: "search", component: () => import("../views/SearchView.vue") },
  { path: "/settings", name: "settings", component: () => import("../views/SettingsView.vue") },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
