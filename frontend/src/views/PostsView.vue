<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import api from "../api";

const route = useRoute();
const posts = ref<any[]>([]);
const subreddits = ref<any[]>([]);
const loading = ref(true);
const sortBy = ref("score");
const order = ref("desc");
const since = ref("all");
const currentSubredditId = ref<number | null>(null);
const minScore = ref<number | null>(null);
const maxScore = ref<number | null>(null);
const compact = ref(false);
const page = ref(0);
const hasMore = ref(true);
const pageSize = 50;

onMounted(() => {
  loadSubreddits();
  const qId = route.query.subreddit_id;
  if (qId) currentSubredditId.value = Number(qId);
  loadPosts();
});

async function loadSubreddits() {
  subreddits.value = await api.getSubreddits();
}

const currentSubredditName = computed(() => {
  if (!currentSubredditId.value) return undefined;
  const sub = subreddits.value.find((s: any) => s.id === currentSubredditId.value);
  return sub?.name;
});
const exportPostsCsv = computed(() => api.exportPostsUrl(currentSubredditName.value, "csv"));
const exportPostsJson = computed(() => api.exportPostsUrl(currentSubredditName.value, "json"));

async function loadPosts(reset = false) {
  if (reset) { page.value = 0; posts.value = []; }
  const params: Record<string, string | number> = {
    sort_by: sortBy.value,
    order: order.value,
    limit: pageSize,
    offset: page.value * pageSize,
  };
  if (currentSubredditId.value) params.subreddit_id = currentSubredditId.value;
  if (since.value && since.value !== "all") params.since = since.value;
  if (minScore.value !== null) params.min_score = minScore.value;
  if (maxScore.value !== null) params.max_score = maxScore.value;

  const batch = await api.getPosts(params);
  posts.value.push(...batch);
  hasMore.value = batch.length === pageSize;
}

function loadMore() {
  page.value++;
  loadPosts();
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

function getThumbUrl(post: any): string | undefined {
  if (post.local_thumbnail) return `/api/thumbnails/${post.reddit_id}`;
  if (post.thumbnail_url && post.thumbnail_url.startsWith("http")) return post.thumbnail_url;
  return undefined;
}

const activeFilterCount = computed(() => {
  let n = 0;
  if (currentSubredditId.value !== null) n++;
  if (minScore.value !== null) n++;
  if (maxScore.value !== null) n++;
  if (since.value !== "all") n++;
  return n;
});

function resetFilters() {
  since.value = "all";
  currentSubredditId.value = null;
  minScore.value = null;
  maxScore.value = null;
  sortBy.value = "score";
  order.value = "desc";
}

function applyScoreFilters() {
  loadPosts(true);
}

watch(sortBy, () => loadPosts(true));
watch(order, () => loadPosts(true));
watch(since, () => loadPosts(true));
watch(currentSubredditId, () => loadPosts(true));
</script>

<template>
  <div class="posts-view">
    <h1>Posts</h1>

    <div class="filters">
      <select v-model="since">
        <option value="all">All time</option>
        <option value="24h">Last 24h</option>
        <option value="7d">Last 7 days</option>
        <option value="30d">Last 30 days</option>
      </select>
      <select v-model="currentSubredditId">
        <option :value="null">All subreddits</option>
        <option v-for="sub in subreddits" :key="sub.id" :value="sub.id">
          /r/{{ sub.name }}
        </option>
      </select>
      <select v-model="sortBy">
        <option value="score">Score</option>
        <option value="date">Date</option>
        <option value="comments">Comments</option>
      </select>
      <button class="btn-order" :class="{ asc: order === 'asc' }" @click="order = order === 'desc' ? 'asc' : 'desc'" :title="order === 'desc' ? 'Descending' : 'Ascending'">
        {{ order === 'desc' ? '↓ Desc' : '↑ Asc' }}
      </button>
      <div class="score-filter">
        <input
          type="number"
          v-model.number="minScore"
          placeholder="Min score"
          class="score-input"
          @change="applyScoreFilters"
        />
        <span class="score-sep">–</span>
        <input
          type="number"
          v-model.number="maxScore"
          placeholder="Max score"
          class="score-input"
          @change="applyScoreFilters"
        />
      </div>
      <button class="btn-toggle-compact" :class="{ active: compact }" @click="compact = !compact">
        {{ compact ? '☷ Normal' : '⊟ Compact' }}
      </button>
      <button
        v-if="activeFilterCount > 0"
        class="btn-reset"
        @click="resetFilters"
        title="Reset all filters"
      >
        ✕ Reset ({{ activeFilterCount }})
      </button>
      <div class="export-group">
        <span class="export-label">Export:</span>
        <a :href="exportPostsCsv" class="btn-export" download>CSV</a>
        <a :href="exportPostsJson" class="btn-export" download>JSON</a>
      </div>
    </div>

    <div v-if="loading && posts.length === 0" class="loading">Loading...</div>

    <div class="post-list" :class="{ compact }">
      <RouterLink
        v-for="post in posts"
        :key="post.id"
        :to="`/posts/${post.id}`"
        class="post-card"
      >
        <div v-if="!compact" class="post-score" :style="{ color: typeColor(post.post_type) }">
          {{ post.score >= 1000 ? (post.score / 1000).toFixed(1) + "k" : post.score }}
          <span class="vote">▲</span>
        </div>
        <img
          v-if="getThumbUrl(post)"
          :src="getThumbUrl(post)"
          alt=""
          class="post-thumb"
          :class="{ compact }"
          loading="lazy"
        />
        <div v-else class="post-thumb-placeholder" :class="{ compact }">
          <span>{{ post.post_type === 'image' ? '🖼' : post.post_type === 'video' ? '🎬' : '📄' }}</span>
        </div>
        <div class="post-body">
          <div class="post-title-row">
            <h3>{{ post.title }}</h3>
            <span
              v-if="post.link_flair_text"
              class="flair-badge"
              :style="{ backgroundColor: post.link_flair_background_color || '#555' }"
            >{{ post.link_flair_text }}</span>
          </div>
          <div class="post-meta">
            <span v-if="compact" class="compact-score" :style="{ color: typeColor(post.post_type) }">
              ▲ {{ post.score >= 1000 ? (post.score / 1000).toFixed(1) + "k" : post.score }}
            </span>
            <span v-if="post.author" class="author">u/{{ post.author }}</span>
            <span>💬 {{ post.num_comments }}</span>
            <span :style="{ color: typeColor(post.post_type) }">{{ post.post_type }}</span>
            <span v-if="post.subreddit">r/{{ post.subreddit.name }}</span>
            <span class="time">{{ timeAgo(post.scraped_at) }}</span>
          </div>
        </div>
      </RouterLink>

      <button v-if="hasMore && posts.length > 0" class="load-more" @click="loadMore">Load more</button>
      <div v-if="posts.length === 0 && !loading" class="empty">No posts yet. Scrape some subreddits!</div>
    </div>
  </div>
</template>

<style scoped>
h1 { font-size: 1.5rem; margin-bottom: 1.5rem; }

.filters {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.filters select {
  padding: 0.5rem 0.75rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 0.85rem;
}

.score-filter {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}
.score-input {
  width: 5rem;
  padding: 0.5rem 0.5rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 0.85rem;
}
.score-input::placeholder {
  color: var(--text-muted);
  font-size: 0.75rem;
}
.score-sep {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.btn-order {
  padding: 0.5rem 0.75rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-order:hover { background: var(--bg-hover); color: var(--text); }
.btn-order.asc { border-color: var(--blue); color: var(--text); }

.btn-reset {
  padding: 0.4rem 0.7rem;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-reset:hover {
  background: var(--bg-hover);
  color: var(--text);
  border-color: #f85149;
}

.export-group {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-left: auto;
}
.export-label {
  font-size: 0.8rem;
  color: var(--text-muted);
}
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
.btn-export:hover {
  background: var(--bg-hover);
}

.post-list { display: flex; flex-direction: column; gap: 0.25rem; }
.post-list.compact { gap: 2px; }

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

/* Compact mode */
.btn-toggle-compact {
  padding: 0.4rem 0.7rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-toggle-compact:hover { background: var(--bg-hover); color: var(--text); }
.btn-toggle-compact.active { background: var(--bg-hover); color: var(--text); border-color: var(--blue); }

.compact .post-card {
  padding: 0.35rem 0.6rem;
  border-radius: 4px;
}
.compact .post-title-row h3 {
  font-size: 0.82rem;
  margin-bottom: 0.1rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.compact .post-meta {
  font-size: 0.7rem;
  gap: 0.5rem;
}
.compact-score {
  font-weight: 700;
  font-size: 0.7rem;
}

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

.post-title-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.post-title-row h3 {
  font-size: 0.9rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.flair-badge {
  display: inline-block;
  padding: 0.1rem 0.45rem;
  border-radius: 10px;
  font-size: 0.65rem;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  line-height: 1.4;
  flex-shrink: 0;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}

.post-thumb {
  width: 60px;
  height: 60px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
  background: var(--bg-hover);
}
.post-thumb.compact {
  width: 36px;
  height: 36px;
  border-radius: 4px;
}
.post-thumb-placeholder {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 6px;
  flex-shrink: 0;
  font-size: 1.2rem;
}
.post-thumb-placeholder.compact {
  width: 36px;
  height: 36px;
  font-size: 0.8rem;
  border-radius: 4px;
}

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
</style>
