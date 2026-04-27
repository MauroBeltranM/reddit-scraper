<script setup lang="ts">
import { ref } from "vue";
import api from "../api";

const query = ref("");
const results = ref<any[]>([]);
const loading = ref(false);
const searched = ref(false);

async function search() {
  const q = query.value.trim();
  if (!q || q.length < 2) return;
  loading.value = true;
  searched.value = true;
  try {
    results.value = await api.searchComments(q);
  } catch {
    results.value = [];
  } finally {
    loading.value = false;
  }
}

function scoreColor(score: number) {
  if (score >= 100) return "#ff4500";
  if (score >= 10) return "#ffd700";
  return "var(--text-muted)";
}
</script>

<template>
  <div class="search-page">
    <h1>Search Comments</h1>

    <div class="search-form">
      <input
        v-model="query"
        placeholder="Search comment text..."
        @keyup.enter="search"
        :disabled="loading"
        autofocus
      />
      <button @click="search" :disabled="loading || query.length < 2">
        {{ loading ? "Searching..." : "Search" }}
      </button>
    </div>

    <div v-if="searched" class="result-count">
      {{ results.length }} results found
    </div>

    <div class="result-list">
      <router-link
        v-for="r in results"
        :key="r.id"
        :to="`/posts/${r.post_id}`"
        class="result-card"
      >
        <div class="result-meta">
          <span v-if="r.author" class="author">u/{{ r.author }}</span>
          <span class="score" :style="{ color: scoreColor(r.score) }">{{ r.score }} ▲</span>
          <span class="depth">depth: {{ r.depth }}</span>
        </div>
        <div class="result-body">{{ r.body }}</div>
      </router-link>

      <div v-if="searched && results.length === 0" class="empty">
        No results. Try different keywords.
      </div>
    </div>
  </div>
</template>

<style scoped>
h1 { font-size: 1.5rem; margin-bottom: 1.5rem; }

.search-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.search-form input {
  flex: 1;
  padding: 0.6rem 0.75rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 0.9rem;
}

.search-form input:focus { outline: none; border-color: var(--accent); }

.search-form button {
  padding: 0.6rem 1.2rem;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
}
.search-form button:disabled { opacity: 0.5; cursor: not-allowed; }

.result-count {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.result-list { display: flex; flex-direction: column; gap: 0.5rem; }

.result-card {
  display: block;
  padding: 0.75rem 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  transition: background 0.15s;
}
.result-card:hover { background: var(--bg-hover); }

.result-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  margin-bottom: 0.3rem;
}

.author { color: var(--blue); }
.score { font-weight: 600; }
.depth { color: var(--text-muted); }

.result-body {
  font-size: 0.8rem;
  line-height: 1.4;
  color: var(--text-muted);
}

.empty { color: var(--text-muted); text-align: center; padding: 2rem; }
</style>
