<script setup lang="ts">
import { ref, onMounted } from "vue";
import { RouterView, RouterLink, useRoute } from "vue-router";

const route = useRoute();

const navItems = [
  { path: "/", label: "Dashboard", icon: "📊" },
  { path: "/subreddits", label: "Subreddits", icon: "📡" },
  { path: "/posts", label: "Posts", icon: "📝" },
  { path: "/search", label: "Search", icon: "🔍" },
  { path: "/settings", label: "Settings", icon: "⚙️" },
];

const isDark = ref(true);

function isActive(path: string) {
  if (path === "/") return route.path === "/";
  return route.path.startsWith(path);
}

function applyTheme(dark: boolean) {
  isDark.value = dark;
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  localStorage.setItem("theme", dark ? "dark" : "light");
}

function toggleTheme() {
  applyTheme(!isDark.value);
}

onMounted(() => {
  const saved = localStorage.getItem("theme");
  if (saved === "light") {
    applyTheme(false);
  } else {
    applyTheme(true);
  }
});
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
      <div class="theme-toggle-wrapper">
        <button class="theme-toggle" @click="toggleTheme" :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'">
          {{ isDark ? '☀️' : '🌙' }}
        </button>
      </div>
    </nav>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style>
/* ===== Light theme (default) ===== */
:root {
  --bg-dark: #f6f8fa;
  --bg-card: #ffffff;
  --bg-hover: #eaeef2;
  --border: #d0d7de;
  --text: #1f2328;
  --text-muted: #656d76;
  --accent: #cf3800;
  --accent-hover: #a82d00;
  --green: #1a7f37;
  --blue: #0969da;
  --shadow: rgba(0, 0, 0, 0.06);
}

/* ===== Dark theme ===== */
[data-theme='dark'] {
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
  --shadow: rgba(0, 0, 0, 0.3);
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
  transition: background 0.2s, color 0.2s;
}

a {
  color: var(--blue);
  text-decoration: none;
}

/* Transition on themed elements */
.theme-transition,
.sidebar,
.stat-card,
.chart-card,
.post-card,
.sub-card,
.settings-form .setting-row,
.oauth-card,
.result-box,
.btn,
input,
select,
button {
  transition: background 0.2s, color 0.2s, border-color 0.2s;
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

.theme-toggle-wrapper {
  margin-top: auto;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border);
}

.theme-toggle {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-hover);
  color: var(--text);
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s;
}

.theme-toggle:hover {
  border-color: var(--accent);
  background: var(--bg-card);
}
</style>
