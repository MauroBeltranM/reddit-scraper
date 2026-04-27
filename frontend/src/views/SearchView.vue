<script setup lang="ts">
import { ref, onMounted } from "vue";
import { RouterLink } from "vue-router";
import api from "../api";

interface SearchResult {
  id: number;
  reddit_id: string;
  post_id: number;
  author: string | null;
  score: number;
  body: string;
  depth: number;
}

const subreddits = ref<{ id: number; name: string }[]>([]);
const query = ref("");
const selectedSub = ref<number | null>(null);
const results = ref<SearchResult[]>([]);
const loading = ref(false);
const searched = ref(false);

async function search() {
  const q = query.value.trim();
  if (!q || q.length < 2) return;
  loading.value = true;
  searched.value = true;
  try {
    results.value = await api.searchComments(q, selectedSub.value ?? undefined);
  } finally {
    loading.value = false;
  }
}

function highlightMatch(text: string) {
  const q = query.value.trim();
  if (!q) return text;
  const regex = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, "gi");
  return text.replace(regex, "<mark>$1</mark>");
}

onMounted(async () => {
  subreddits.value = await api.getSubreddits();
});
</script>

<template>
  <div class="search-view">
    <h1>Search Comments</h1>

    <div class="search-bar">
      <input
        v-model="query"
        placeholder="Search comment text..."
        @keyup.enter="search"
        class="input"
      />
      <select v-model="selectedSub" class="select">
        <option :value="null">All subreddits</option>
        <option v-for="sub in subreddits" :key="sub.id" :value="sub.id">
          r/{{ sub.name }}
        </option>
      </select>
      <button @click="search" :disabled="loading" class="btn btn-accent">
        {{ loading ? "..." : "Search" }}
      </button>
    </div>

    <div v-if="!searched" class="hint">
      Enter at least 2 characters to search across all scraped comments.
    </div>

    <div v-else-if="loading" class="loading">Searching...</div>

    <div v-else-if="!results.length" class="empty">
      No comments found for "{{ query }}"
    </div>

    <div v-else class="results">
      <div class="results-count">{{ results.length }} results</div>
      <RouterLink
        v-for="r in results"
        :key="r.id"
        :to="`/posts/${r.post_id}`"
        class="result-card"
      >
        <div class="result-body" v-html="highlightMatch(r.body)"></div>
        <div class="result-meta">
          <span v-if="r.author" class="author">u/{{ r.author }}</span>
          <span>{{ r.score }} ▲</span>
          <span>depth {{ r.depth }}</span>
        </div>
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
h1 { margin-bottom: 1rem; }

.search-bar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 0.9rem;
}

.input:focus { outline: none; border-color: var(--accent); }

.select {
  padding: 0.5rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 0.85rem;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-accent {
  background: var(--accent);
  color: white;
}

.hint { color: var(--text-muted); font-size: 0.85rem; }

.results-count {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.results {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.result-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.75rem;
  color: var(--text);
  transition: border-color 0.15s;
}

.result-card:hover { border-color: var(--accent); }

.result-body {
  font-size: 0.9rem;
  line-height: 1.5;
  margin-bottom: 0.3rem;
  overflow-wrap: break-word;
}

.result-body :deep(mark) {
  background: #ff450040;
  color: var(--text);
  border-radius: 2px;
  padding: 0 2px;
}

.result-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.author { color: var(--blue); }

.empty { color: var(--text-muted); text-align: center; padding: 2rem; }
.loading { color: var(--text-muted); }
</style>
