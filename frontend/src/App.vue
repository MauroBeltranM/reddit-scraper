<script setup lang="ts">
import { RouterView, RouterLink, useRoute } from "vue-router";

const route = useRoute();

const navItems = [
  { path: "/", label: "Dashboard", icon: "📊" },
  { path: "/subreddits", label: "Subreddits", icon: "📡" },
  { path: "/posts", label: "Posts", icon: "📝" },
  { path: "/search", label: "Search", icon: "🔍" },
];

function isActive(path: string) {
  if (path === "/") return route.path === "/";
  return route.path.startsWith(path);
}
</script>

<template>
  <div class="app">
    <nav class="sidebar">
      <div class="logo">
        <h1>🔎 Reddit Scraper</h1>
      </div>
      <div class="nav-links">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="{ active: isActive(item.path) }"
          class="nav-link"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          {{ item.label }}
        </RouterLink>
      </div>
    </nav>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style>
:root {
  --bg-dark: #0d1117;
  --bg-card: #161b22;
  --bg-hover: #1c2128;
  --border: #30363d;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --accent: #ff4500;
  --accent-hover: #ff6633;
  --green: #3fb950;
  --blue: #58a6ff;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg-dark);
  color: var(--text);
}

a {
  color: var(--blue);
  text-decoration: none;
}
</style>

<style scoped>
.app {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 220px;
  background: var(--bg-card);
  border-right: 1px solid var(--border);
  padding: 1.5rem 1rem;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
}

.logo h1 {
  font-size: 1.1rem;
  color: var(--accent);
  margin-bottom: 2rem;
}

.nav-links {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 0.9rem;
  transition: all 0.15s;
}

.nav-link:hover {
  background: var(--bg-hover);
  color: var(--text);
}

.nav-link.active {
  background: var(--bg-hover);
  color: var(--text);
  font-weight: 600;
}

.content {
  margin-left: 220px;
  flex: 1;
  padding: 2rem;
  max-width: 1100px;
}

.nav-icon {
  font-size: 1.1rem;
}
</style>
