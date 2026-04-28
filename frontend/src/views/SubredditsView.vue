<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import api from "../api";

interface Subreddit {
  id: number;
  name: string;
  active: boolean;
  last_scraped_at: string | null;
  total_posts: number;
}

interface ProgressData {
  task_id: string;
  subreddit: string;
  status: string;
  progress: number;
  total: number;
  current_post: string;
  posts_found: number;
  posts_new: number;
  comments_total: number;
  duration_sec: number;
  error: string;
}

const subreddits = ref<Subreddit[]>([]);
const newSub = ref("");
const loading = ref(true);
const scraping = ref<string | null>(null);
const scrapingAll = ref(false);
const lastResult = ref<string | null>(null);
const progressData = ref<ProgressData | null>(null);

let eventSource: EventSource | null = null;

async function load() {
  subreddits.value = await api.getSubreddits();
  loading.value = false;
}

async function add() {
  const name = newSub.value.trim().toLowerCase().replace(/^r\//, "");
  if (!name) return;
  newSub.value = "";
  try {
    await api.addSubreddit(name);
    await load();
  } catch (e: any) {
    alert(e.response?.data?.detail || "Error adding subreddit");
  }
}

async function remove(id: number) {
  if (!confirm("Remove this subreddit and all its data?")) return;
  await api.removeSubreddit(id);
  await load();
}

function closeEventSource() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

async function scrape(name: string) {
  scraping.value = name;
  lastResult.value = null;
  progressData.value = null;
  closeEventSource();

  try {
    // Start the scrape (returns immediately with task_id)
    await api.scrape(name);

    // Connect to SSE for progress
    eventSource = api.scrapeProgress(name);
    eventSource.onmessage = (event) => {
      const data: ProgressData = JSON.parse(event.data);
      progressData.value = data;

      if (data.status === "done") {
        lastResult.value = `${data.subreddit}: ${data.posts_new} new posts, ${data.comments_total} comments (${data.duration_sec}s)`;
        closeEventSource();
        scraping.value = null;
        load();
      } else if (data.status === "error") {
        lastResult.value = `Error: ${data.error}`;
        closeEventSource();
        scraping.value = null;
      }
    };
    eventSource.onerror = () => {
      closeEventSource();
      scraping.value = null;
    };
  } catch (e: any) {
    lastResult.value = `Error: ${e.response?.data?.detail || e.message}`;
    scraping.value = null;
  }
}

async function scrapeAll() {
  scrapingAll.value = true;
  lastResult.value = null;
  progressData.value = null;
  closeEventSource();

  try {
    const res = await api.scrapeAll();
    // For scrape-all, we just wait a bit and reload
    // The tasks run in parallel, poll the last subreddit's progress
    if (res.tasks && res.tasks.length > 0) {
      // We'll just show a generic progress state
      scraping.value = "all";
    }

    // Simple approach: check every 2s if all tasks are done
    const checkDone = async () => {
      let allDone = false;
      while (!allDone) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          await load();
          // Check if any subreddit is still being scraped
          allDone = !scraping.value;
        } catch {
          allDone = true;
        }
      }
      scrapingAll.value = false;
      scraping.value = null;
      lastResult.value = `Scrape complete. Data refreshed.`;
      await load();
    };
    checkDone();
  } catch (e: any) {
    lastResult.value = `Error: ${e.message}`;
    scrapingAll.value = false;
    scraping.value = null;
  }
}

function formatDate(d: string | null) {
  if (!d) return "Never";
  return new Date(d).toLocaleString();
}

onMounted(load);
onUnmounted(closeEventSource);
</script>

<template>
  <div class="subreddits-view">
    <h1>Subreddits</h1>

    <div class="add-bar">
      <input
        v-model="newSub"
        placeholder="r/..."
        @keyup.enter="add"
        class="input"
      />
      <button @click="add" class="btn btn-accent">Add</button>
      <button @click="scrapeAll" :disabled="scrapingAll" class="btn btn-secondary">
        {{ scrapingAll ? "Scraping..." : "Scrape All" }}
      </button>
    </div>

    <!-- Progress indicator -->
    <div v-if="progressData && progressData.status === 'running'" class="result-box progress-box">
      <div class="progress-header">
        🔄 Scraping r/{{ progressData.subreddit }}
        <span class="progress-count">{{ progressData.progress }} / {{ progressData.total }}</span>
      </div>
      <div class="progress-bar-track">
        <div
          class="progress-bar-fill"
          :style="{ width: progressData.total ? (progressData.progress / progressData.total * 100) + '%' : '0%' }"
        ></div>
      </div>
      <div v-if="progressData.current_post" class="progress-detail">
        {{ progressData.current_post }}
      </div>
    </div>

    <div v-if="lastResult" class="result-box">
      <pre>{{ lastResult }}</pre>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else class="sub-list">
      <div v-for="sub in subreddits" :key="sub.id" class="sub-card">
        <div class="sub-info">
          <RouterLink :to="{ path: '/posts', query: { subreddit_id: sub.id } }" class="sub-name">
            r/{{ sub.name }}
          </RouterLink>
          <div class="sub-meta">
            {{ sub.total_posts }} posts · Last scraped: {{ formatDate(sub.last_scraped_at) }}
          </div>
        </div>
        <div class="sub-actions">
          <button
            @click="scrape(sub.name)"
            :disabled="scraping === sub.name"
            class="btn btn-small"
          >
            {{ scraping === sub.name ? "..." : "Scrape" }}
          </button>
          <button @click="remove(sub.id)" class="btn btn-small btn-danger">✕</button>
        </div>
      </div>

      <div v-if="!subreddits.length" class="empty">
        No subreddits yet. Add one above to start scraping.
      </div>
    </div>
  </div>
</template>

<style scoped>
h1 { margin-bottom: 1rem; }

.add-bar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
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

.input:focus {
  outline: none;
  border-color: var(--accent);
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.15s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-accent {
  background: var(--accent);
  color: white;
}

.btn-accent:hover { background: var(--accent-hover); }

.btn-secondary {
  background: var(--bg-hover);
  color: var(--text);
  border: 1px solid var(--border);
}

.btn-small {
  padding: 0.3rem 0.6rem;
  font-size: 0.8rem;
}

.btn-danger {
  background: transparent;
  color: #f85149;
  border: 1px solid #f85149;
}

.btn-danger:hover {
  background: #f8514920;
}

.result-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.75rem;
  margin-bottom: 1rem;
  font-size: 0.8rem;
  white-space: pre-wrap;
}

.result-box pre {
  color: var(--green);
  margin: 0;
}

.sub-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sub-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.75rem 1rem;
}

.sub-name {
  font-weight: 600;
  font-size: 1rem;
}

.sub-meta {
  color: var(--text-muted);
  font-size: 0.8rem;
  margin-top: 0.15rem;
}

.sub-actions {
  display: flex;
  gap: 0.4rem;
}

.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 2rem;
}

.loading { color: var(--text-muted); }

/* Progress styles */
.progress-box {
  border-color: var(--accent);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.progress-count {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.progress-bar-track {
  width: 100%;
  height: 6px;
  background: var(--bg-hover);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-detail {
  color: var(--text-muted);
  font-size: 0.75rem;
  margin-top: 0.4rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
