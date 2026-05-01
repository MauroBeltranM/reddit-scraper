<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import api from "../api";

const route = useRoute();
const posts = ref<any[]>([]);
const subreddits = ref<any[]>([]);
const loading = ref(true);
const sort = ref("score");
const currentSubredditId = ref<number | null>(null);
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
    sort: sort.value,
    limit: pageSize,
    offset: page.value * pageSize,
  };
  if (currentSubredditId.value) params.subreddit_id = currentSubredditId.value;

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

watch(sort, () => loadPosts(true));
watch(currentSubredditId, () => loadPosts(true));
</script>

<template>
  <div class="posts-view">
    <h1>Posts</h1>

    <div class="filters">
      <select v-model="currentSubredditId">
        <option :value="null">All subreddits</option>
        <option v-for="sub in subreddits" :key="sub.id" :value="sub.id">
          /r/{{ sub.name }}
        </option>
      </select>
      <select v-model="sort">
        <option value="score">Top by Score</option>
        <option value="new">Newest</option>
        <option value="comments">Most Comments</option>
      </select>
      <div class="export-group">
        <span class="export-label">Export:</span>
        <a :href="exportPostsCsv" class="btn-export" download>CSV</a>
        <a :href="exportPostsJson" class="btn-export" download>JSON</a>
      </div>
    </div>

    <div v-if="loading && posts.length === 0" class="loading">Loading...</div>

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
</style>
