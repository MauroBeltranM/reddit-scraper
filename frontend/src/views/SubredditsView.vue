<script setup lang="ts">
import { ref, onMounted } from "vue";
import api from "../api";

const subreddits = ref<any[]>([]);
const newSub = ref("");
const loading = ref(false);
const scraping = ref<string | null>(null);
const scrapeAllLoading = ref(false);
const scrapeResult = ref<any>(null);

onMounted(loadSubreddits);

async function loadSubreddits() {
  subreddits.value = await api.getSubreddits();
}

async function addSubreddit() {
  const name = newSub.value.trim().toLowerCase();
  if (!name) return;
  loading.value = true;
  try {
    await api.addSubreddit(name);
    newSub.value = "";
    await loadSubreddits();
  } catch (e: any) {
    alert(e.response?.data?.detail || "Failed to add subreddit");
  } finally {
    loading.value = false;
  }
}

async function removeSub(id: number) {
  if (!confirm("Remove this subreddit and all its data?")) return;
  await api.removeSubreddit(id);
  await loadSubreddits();
}

async function scrape(name: string) {
  scraping.value = name;
  scrapeResult.value = null;
  try {
    scrapeResult.value = await api.scrape(name);
    await loadSubreddits();
  } catch (e: any) {
    alert(e.response?.data?.detail || "Scrape failed");
  } finally {
    scraping.value = null;
  }
}

async function scrapeAll() {
  scrapeAllLoading.value = true;
  scrapeResult.value = null;
  try {
    const data = await api.scrapeAll();
    scrapeResult.value = data;
    await loadSubreddits();
  } catch (e: any) {
    alert("Scrape all failed");
  } finally {
    scrapeAllLoading.value = false;
  }
}

function formatDate(d: string) {
  if (!d) return "Never";
  return new Date(d).toLocaleString();
}
</script>

<template>
  <div class="subreddits-page">
    <h1>Subreddits</h1>

    <div class="add-form">
      <input
        v-model="newSub"
        placeholder="e.g. programming"
        @keyup.enter="addSubreddit"
        :disabled="loading"
      />
      <button @click="addSubreddit" :disabled="loading || !newSub.trim()">
        {{ loading ? "Adding..." : "Add" }}
      </button>
    </div>

    <div class="actions">
      <button class="btn-scrape-all" @click="scrapeAll" :disabled="scrapeAllLoading || subreddits.length === 0">
        {{ scrapeAllLoading ? "Scraping..." : "⚡ Scrape All" }}
      </button>
    </div>

    <div v-if="scrapeResult" class="scrape-result">
      <strong>Scrape result:</strong>
      <pre>{{ JSON.stringify(scrapeResult, null, 2) }}</pre>
    </div>

    <div class="sub-list">
      <div v-for="sub in subreddits" :key="sub.id" class="sub-card">
        <div class="sub-info">
          <h3>/r/{{ sub.name }}</h3>
          <span class="sub-meta">
            {{ sub.total_posts }} posts · Last scraped: {{ formatDate(sub.last_scraped_at) }}
          </span>
        </div>
        <div class="sub-actions">
          <button
            class="btn-scrape"
            @click="scrape(sub.name)"
            :disabled="scraping === sub.name"
          >
            {{ scraping === sub.name ? "Scraping..." : "Scrape" }}
          </button>
          <button class="btn-remove" @click="removeSub(sub.id)">✕</button>
        </div>
      </div>
      <div v-if="subreddits.length === 0" class="empty">
        No subreddits yet. Add one above!
      </div>
    </div>
  </div>
</template>

<style scoped>
h1 { font-size: 1.5rem; margin-bottom: 1.5rem; }

.add-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.add-form input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 0.9rem;
}

.add-form input:focus { outline: none; border-color: var(--accent); }

button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  transition: all 0.15s;
}

button:disabled { opacity: 0.5; cursor: not-allowed; }

.add-form button { background: var(--accent); color: white; }
.add-form button:hover:not(:disabled) { background: var(--accent-hover); }

.actions { margin-bottom: 1.5rem; }

.btn-scrape-all {
  background: var(--green);
  color: #000;
}
.btn-scrape-all:hover:not(:disabled) { background: #4cca5c; }

.sub-list { display: flex; flex-direction: column; gap: 0.5rem; }

.sub-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.sub-info h3 { font-size: 1rem; color: var(--accent); }
.sub-meta { font-size: 0.8rem; color: var(--text-muted); }

.sub-actions { display: flex; gap: 0.5rem; }

.btn-scrape { background: var(--blue); color: #000; }
.btn-scrape:hover:not(:disabled) { background: #79b8ff; }
.btn-remove { background: transparent; color: var(--text-muted); border: 1px solid var(--border); }
.btn-remove:hover { color: #f85149; border-color: #f85149; }

.scrape-result {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  font-size: 0.8rem;
}

.scrape-result pre {
  white-space: pre-wrap;
  color: var(--green);
  margin-top: 0.5rem;
}

.empty { color: var(--text-muted); text-align: center; padding: 2rem; }
</style>
