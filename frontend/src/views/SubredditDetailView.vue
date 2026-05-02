<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import api from "../api";

interface SubredditStats {
  id: number;
  name: string;
  active: boolean;
  total_posts: number;
  total_comments: number;
  last_scraped_at: string | null;
  created_at: string;
  top_post_title: string | null;
  top_post_score: number | null;
  avg_score: number | null;
  avg_comments: number | null;
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

const route = useRoute();
const stats = ref<SubredditStats | null>(null);
const posts = ref<any[]>([]);
const loadingStats = ref(true);
const loadingPosts = ref(true);
const sort = ref("score");
const page = ref(0);
const hasMore = ref(true);
const pageSize = 50;
const scraping = ref(false);
const progressData = ref<ProgressData | null>(null);
const lastResult = ref<string | null>(null);

let eventSource: EventSource | null = null;

const subredditId = computed(() => Number(route.params.id));

onMounted(() => {
  loadStats();
  loadPosts();
});

watch(() => route.params.id, () => {
  if (route.params.id) {
    page.value = 0;
    posts.value = [];
    loadStats();
    loadPosts(true);
  }
});

async function loadStats() {
  loadingStats.value = true;
  try {
    stats.value = await api.getSubredditStats(subredditId.value);
  } catch {
    stats.value = null;
  }
  loadingStats.value = false;
}

async function loadPosts(reset = false) {
  if (reset) { page.value = 0; posts.value = []; }
  loadingPosts.value = true;
  const params: Record<string, string | number> = {
    subreddit_id: subredditId.value,
    sort: sort.value,
    limit: pageSize,
    offset: page.value * pageSize,
  };
  try {
    const batch = await api.getPosts(params);
    posts.value.push(...batch);
    hasMore.value = batch.length === pageSize;
  } finally {
    loadingPosts.value = false;
  }
}

function loadMore() {
  page.value++;
  loadPosts();
}

function closeEventSource() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

async function scrapeSubreddit() {
  if (!stats.value) return;
  scraping.value = true;
  lastResult.value = null;
  progressData.value = null;
  closeEventSource();

  try {
    await api.scrape(stats.value.name);
    eventSource = api.scrapeProgress(stats.value.name);
    eventSource.onmessage = (event) => {
      const data: ProgressData = JSON.parse(event.data);
      progressData.value = data;

      if (data.status === "done") {
        lastResult.value = `${data.posts_new} new posts, ${data.comments_total} comments (${data.duration_sec}s)`;
        closeEventSource();
        scraping.value = false;
        loadStats();
        loadPosts(true);
      } else if (data.status === "error") {
        lastResult.value = `Error: ${data.error}`;
        closeEventSource();
        scraping.value = false;
      }
    };
    eventSource.onerror = () => {
      closeEventSource();
      scraping.value = false;
    };
  } catch (e: any) {
    lastResult.value = `Error: ${e.response?.data?.detail || e.message}`;
    scraping.value = false;
  }
}

function formatDate(d: string | null) {
  if (!d) return "Never";
  return new Date(d).toLocaleString();
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function typeColor(type: string) {
  const colors: Record<string, string> = {
    link: "#58a6ff",
    self: "#3fb950",
    image: "#bc8cff",
    video: "#f0883e",
  };
  return colors[type] || "var(--text-muted)";
}

const exportCsv = computed(() => stats.value ? api.exportPostsUrl(stats.value.name, "csv") : "#");
const exportJson = computed(() => stats.value ? api.exportPostsUrl(stats.value.name, "json") : "#");

watch(sort, () => loadPosts(true));

onUnmounted(closeEventSource);
</script>

<template>
  <div class="subreddit-detail">
    <div class="header">
      <RouterLink to="/subreddits" class="back-link">← Subreddits</RouterLink>
    </div>

    <div v-if="loadingStats && !stats" class="loading">Loading...</div>

    <template v-if="stats">
      <div class="sub-header">
        <h1>r/{{ stats.name }}</h1>
        <div class="header-actions">
          <button @click="scrapeSubreddit" :disabled="scraping" class="btn btn-accent">
            {{ scraping ? "Scraping..." : "⚡ Scrape Now" }}
          </button>
          <span class="status-badge" :class="{ active: stats.active }">
            {{ stats.active ? "Active" : "Inactive" }}
          </span>
        </div>
      </div>

      <!-- Progress indicator -->
      <div v-if="progressData && progressData.status === 'running'" class="result-box progress-box">
        <div class="progress-header">
          <div class="spinner-label">
            <span class="spinner"></span>
            <span>Scraping r/{{ stats.name }}</span>
          </div>
          <span class="progress-count">{{ progressData.progress }} / {{ progressData.total }}</span>
        </div>
        <div class="progress-bar-track">
          <div
            class="progress-bar-fill"
            :style="{ width: progressData.total ? (progressData.progress / progressData.total * 100) + '%' : '0%' }"
          ></div>
        </div>
        <div v-if="progressData.current_post" class="progress-detail">
          📄 {{ progressData.progress }}/{{ progressData.total }}: {{ progressData.current_post }}
        </div>
        <div class="progress-stats">
          <span>🆕 {{ progressData.posts_new }} new</span>
          <span>💬 {{ progressData.comments_total }} comments</span>
          <span>⏱ {{ progressData.duration_sec ? progressData.duration_sec.toFixed(1) + 's' : '...' }}</span>
        </div>
      </div>

      <div v-if="lastResult" class="result-box">
        <pre>{{ lastResult }}</pre>
      </div>

      <!-- Stats cards -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_posts }}</div>
          <div class="stat-label">Total Posts</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_comments }}</div>
          <div class="stat-label">Total Comments</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.avg_score ?? '—' }}</div>
          <div class="stat-label">Avg Score</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.avg_comments ?? '—' }}</div>
          <div class="stat-label">Avg Comments</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ formatDate(stats.last_scraped_at) }}</div>
          <div class="stat-label">Last Scraped</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ formatDate(stats.created_at) }}</div>
          <div class="stat-label">Added</div>
        </div>
      </div>

      <!-- Top post highlight -->
      <div v-if="stats.top_post_title" class="top-post-highlight">
        <span class="top-label">🏆 Top Post</span>
        <span class="top-title">{{ stats.top_post_title }}</span>
        <span class="top-score">{{ stats.top_post_score }} points</span>
      </div>

      <!-- Posts section -->
      <div class="posts-section">
        <div class="section-header">
          <h2>Posts</h2>
          <div class="section-actions">
            <select v-model="sort">
              <option value="score">Top by Score</option>
              <option value="new">Newest</option>
              <option value="comments">Most Comments</option>
            </select>
            <div class="export-group">
              <span class="export-label">Export:</span>
              <a :href="exportCsv" class="btn-export" download>CSV</a>
              <a :href="exportJson" class="btn-export" download>JSON</a>
            </div>
          </div>
        </div>

        <div v-if="loadingPosts && posts.length === 0" class="loading">Loading posts...</div>

        <div class="post-list">
          <RouterLink
            v-for="post in posts"
            :key="post.id"
            :to="`/posts/${post.id}`"
            class="post-card"
          >
            <div class="post-score" :style="{ color: typeColor(post.post_type) }">
              {{ post.score >= 1000 ? (post.score / 1000).toFixed(1) + "k" : post.score }}
              <span class="vote">▲</span>
            </div>
            <div class="post-body">
              <h3>{{ post.title }}</h3>
              <div class="post-meta">
                <span v-if="post.author" class="author">u/{{ post.author }}</span>
                <span>💬 {{ post.num_comments }}</span>
                <span :style="{ color: typeColor(post.post_type) }">{{ post.post_type }}</span>
                <span class="time">{{ timeAgo(post.scraped_at) }}</span>
              </div>
            </div>
          </RouterLink>

          <button v-if="hasMore && posts.length > 0" class="load-more" @click="loadMore">Load more</button>
          <div v-if="posts.length === 0 && !loadingPosts" class="empty">No posts yet. Hit "Scrape Now" to get started!</div>
        </div>
      </div>
    </template>

    <div v-if="!loadingStats && !stats" class="error">
      Subreddit not found. <RouterLink to="/subreddits">Back to list</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.subreddit-detail { max-width: 900px; }

.header { margin-bottom: 1rem; }
.back-link {
  color: var(--text-muted);
  font-size: 0.85rem;
  transition: color 0.15s;
}
.back-link:hover { color: var(--text); }

.sub-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
.sub-header h1 {
  font-size: 1.5rem;
  color: var(--accent);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
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
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-accent { background: var(--accent); color: white; }
.btn-accent:hover:not(:disabled) { background: var(--accent-hover); }

.status-badge {
  padding: 0.25rem 0.6rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--bg-hover);
  color: var(--text-muted);
  border: 1px solid var(--border);
}
.status-badge.active {
  background: #3fb95020;
  color: var(--green);
  border-color: #3fb95040;
}

/* Stats grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  text-align: center;
}
.stat-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 0.25rem;
}
.stat-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Top post */
.top-post-highlight {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: var(--bg-card);
  border: 1px solid #daa52040;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  margin-bottom: 1.5rem;
}
.top-label {
  font-size: 0.8rem;
  color: #daa520;
  white-space: nowrap;
}
.top-title {
  flex: 1;
  font-size: 0.85rem;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top-score {
  font-size: 0.8rem;
  color: var(--text-muted);
  white-space: nowrap;
}

/* Progress */
.result-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.75rem;
  margin-bottom: 1rem;
  font-size: 0.8rem;
  white-space: pre-wrap;
}
.result-box pre { color: var(--green); margin: 0; }
.progress-box { border-color: var(--accent); }
.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}
.spinner-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.progress-count { font-size: 0.8rem; color: var(--text-muted); }
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
.progress-stats {
  display: flex;
  gap: 1rem;
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Posts section */
.posts-section { margin-top: 0.5rem; }
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.section-header h2 { font-size: 1.15rem; }
.section-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.section-actions select {
  padding: 0.4rem 0.6rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 0.8rem;
}
.export-group {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.export-label { font-size: 0.8rem; color: var(--text-muted); }
.btn-export {
  padding: 0.35rem 0.65rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 0.8rem;
  text-decoration: none;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-export:hover { background: var(--bg-hover); }

/* Post list */
.post-list { display: flex; flex-direction: column; gap: 0.25rem; }
.post-card {
  display: flex;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  transition: background 0.15s;
}
.post-card:hover { background: var(--bg-hover); }
.post-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 50px;
  font-weight: 700;
  font-size: 1rem;
}
.vote { font-size: 0.7rem; color: var(--text-muted); }
.post-body { flex: 1; min-width: 0; }
.post-body h3 { font-size: 0.9rem; font-weight: 600; margin-bottom: 0.25rem; }
.post-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}
.author { color: var(--blue); }
.time { margin-left: auto; }

.load-more {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  cursor: pointer;
}
.load-more:hover { background: var(--bg-hover); }
.empty { color: var(--text-muted); text-align: center; padding: 2rem; }
.loading { color: var(--text-muted); }
.error { color: #f85149; padding: 2rem; text-align: center; }

@media (max-width: 700px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .sub-header { flex-direction: column; gap: 0.75rem; align-items: flex-start; }
  .section-header { flex-direction: column; gap: 0.5rem; align-items: flex-start; }
}
</style>
