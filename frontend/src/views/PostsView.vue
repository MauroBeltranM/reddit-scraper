<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import api from "../api";

interface Post {
  id: number;
  reddit_id: string;
  title: string;
  author: string | null;
  score: number;
  num_comments: number;
  post_type: string;
  permalink: string;
  scraped_at: string;
  subreddit: { id: number; name: string } | null;
}

const route = useRoute();
const posts = ref<Post[]>([]);
const subreddits = ref<{ id: number; name: string }[]>([]);
const loading = ref(true);
const sortBy = ref("score");
const currentSubredditId = ref<number | null>(null);

async function loadSubreddits() {
  subreddits.value = await api.getSubreddits();
}

async function loadPosts() {
  loading.value = true;
  const params: Record<string, string | number> = { sort: sortBy.value, limit: 100 };
  if (currentSubredditId.value) {
    params.subreddit_id = currentSubredditId.value;
  }
  posts.value = await api.getPosts(params);
  loading.value = false;
}

function setSubreddit(id: number | null) {
  currentSubredditId.value = id;
  loadPosts();
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function typeBadge(type: string) {
  const colors: Record<string, string> = {
    link: "#58a6ff",
    self: "#3fb950",
    image: "#bc8cff",
    video: "#f0883e",
  };
  return colors[type] || "var(--text-muted)";
}

onMounted(() => {
  loadSubreddits();
  const qId = route.query.subreddit_id;
  if (qId) currentSubredditId.value = Number(qId);
  loadPosts();
});
</script>

<template>
  <div class="posts-view">
    <h1>Posts</h1>

    <div class="toolbar">
      <select v-model="sortBy" @change="loadPosts" class="select">
        <option value="score">Top by Score</option>
        <option value="new">Newest</option>
        <option value="comments">Most Comments</option>
      </select>

      <div class="filter-pills">
        <button
          @click="setSubreddit(null)"
          :class="['pill', { active: !currentSubredditId }]"
        >
          All
        </button>
        <button
          v-for="sub in subreddits"
          :key="sub.id"
          @click="setSubreddit(sub.id)"
          :class="['pill', { active: currentSubredditId === sub.id }]"
        >
          r/{{ sub.name }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else class="post-list">
      <RouterLink
        v-for="post in posts"
        :key="post.id"
        :to="`/posts/${post.id}`"
        class="post-card"
      >
        <div class="post-score">
          <span class="score-num">{{ post.score.toLocaleString() }}</span>
          <span class="score-label">▲</span>
        </div>
        <div class="post-body">
          <div class="post-title">{{ post.title }}</div>
          <div class="post-meta">
            <span :style="{ color: typeBadge(post.post_type) }" class="type-badge">{{ post.post_type }}</span>
            <span v-if="post.subreddit" class="sub">r/{{ post.subreddit.name }}</span>
            <span v-if="post.author">by u/{{ post.author }}</span>
            <span>💬 {{ post.num_comments }}</span>
            <span>{{ timeAgo(post.scraped_at) }}</span>
          </div>
        </div>
      </RouterLink>

      <div v-if="!posts.length" class="empty">
        No posts yet. Scrape a subreddit first.
      </div>
    </div>
  </div>
</template>

<style scoped>
h1 { margin-bottom: 1rem; }

.toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.select {
  padding: 0.4rem 0.6rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 0.85rem;
}

.filter-pills {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
}

.pill {
  padding: 0.3rem 0.7rem;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
}

.pill:hover { background: var(--bg-hover); color: var(--text); }
.pill.active { background: var(--accent); color: white; border-color: var(--accent); }

.post-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.post-card {
  display: flex;
  gap: 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.75rem;
  color: var(--text);
  transition: background 0.15s;
}

.post-card:hover {
  background: var(--bg-hover);
  border-color: var(--accent);
}

.post-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
  color: var(--accent);
}

.score-num { font-weight: 700; font-size: 1rem; }
.score-label { font-size: 0.75rem; color: var(--text-muted); }

.post-body { flex: 1; min-width: 0; }

.post-title {
  font-weight: 500;
  font-size: 0.95rem;
  line-height: 1.3;
  margin-bottom: 0.3rem;
}

.post-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.type-badge {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.7rem;
}

.empty { text-align: center; color: var(--text-muted); padding: 2rem; }
.loading { color: var(--text-muted); }
</style>
