<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import api from "../api";

const posts = ref<any[]>([]);
const subreddits = ref<any[]>([]);
const loading = ref(true);
const sort = ref("score");
const subredditFilter = ref<number | null>(null);
const page = ref(0);
const hasMore = ref(true);
const pageSize = 50;

onMounted(load);

async function load() {
  loading.value = true;
  subreddits.value = await api.getSubreddits();
  await loadPosts();
  loading.value = false;
}

async function loadPosts(reset = false) {
  if (reset) { page.value = 0; posts.value = []; }
  const params: Record<string, string | number> = {
    sort: sort.value,
    limit: pageSize,
    offset: page.value * pageSize,
  };
  if (subredditFilter.value) params.subreddit_id = subredditFilter.value;

  const batch = await api.getPosts(params);
  posts.value.push(...batch);
  hasMore.value = batch.length === pageSize;
}

function loadMore() {
  page.value++;
  loadPosts();
}

function scoreColor(score: number) {
  if (score >= 10000) return "#ff4500";
  if (score >= 1000) return "#ff8c00";
  if (score >= 100) return "#ffd700";
  return "var(--text-muted)";
}

watch(sort, () => loadPosts(true));
watch(subredditFilter, () => loadPosts(true));
</script>

<template>
  <div class="posts-page">
    <h1>Posts</h1>

    <div class="filters">
      <select v-model="subredditFilter">
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
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else class="post-list">
      <router-link
        v-for="post in posts"
        :key="post.id"
        :to="`/posts/${post.id}`"
        class="post-card"
      >
        <div class="post-score" :style="{ color: scoreColor(post.score) }">
          {{ post.score >= 1000 ? (post.score / 1000).toFixed(1) + "k" : post.score }}
          <span class="post-score-label">▲</span>
        </div>
        <div class="post-body">
          <h3>{{ post.title }}</h3>
          <div class="post-meta">
            <span v-if="post.author">u/{{ post.author }}</span>
            <span>💬 {{ post.num_comments }}</span>
            <span>{{ post.post_type }}</span>
            <span v-if="post.subreddit">/r/{{ post.subreddit.name }}</span>
          </div>
        </div>
      </router-link>

      <button v-if="hasMore" class="load-more" @click="loadMore">Load more</button>
      <div v-if="posts.length === 0" class="empty">No posts yet. Scrape some subreddits!</div>
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

.post-score-label { font-size: 0.7rem; color: var(--text-muted); }

.post-body { flex: 1; min-width: 0; }
.post-body h3 { font-size: 0.9rem; font-weight: 600; margin-bottom: 0.25rem; }

.post-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

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
