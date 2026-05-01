<script setup lang="ts">
import { ref, onMounted } from "vue";
import { RouterLink } from "vue-router";
import api from "../api";

interface CommentResult {
  id: number;
  reddit_id: string;
  post_id: number;
  author: string | null;
  score: number;
  body: string;
  depth: number;
}

interface PostResult {
  id: number;
  reddit_id: string;
  subreddit_id: number;
  title: string;
  author: string | null;
  score: number;
  num_comments: number;
  post_type: string;
  subreddit: { id: number; name: string } | null;
  scraped_at: string;
}

const subreddits = ref<{ id: number; name: string }[]>([]);
const query = ref("");
const selectedSub = ref<number | null>(null);
const searchMode = ref<"posts" | "comments">("posts");
const postResults = ref<PostResult[]>([]);
const commentResults = ref<CommentResult[]>([]);
const loading = ref(false);
const searched = ref(false);

async function search() {
  const q = query.value.trim();
  if (!q || q.length < 2) return;
  loading.value = true;
  searched.value = true;
  try {
    if (searchMode.value === "posts") {
      postResults.value = await api.searchPosts(q, selectedSub.value ?? undefined);
      commentResults.value = [];
    } else {
      commentResults.value = await api.searchComments(q, selectedSub.value ?? undefined);
      postResults.value = [];
    }
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

onMounted(async () => {
  subreddits.value = await api.getSubreddits();
});
</script>

<template>
  <div class="search-view">
    <h1>Search</h1>

    <div class="search-bar">
      <div class="mode-toggle">
        <button
          :class="['mode-btn', { active: searchMode === 'posts' }]"
          @click="searchMode = 'posts'"
        >Posts</button>
        <button
          :class="['mode-btn', { active: searchMode === 'comments' }]"
          @click="searchMode = 'comments'"
        >Comments</button>
      </div>
      <input
        v-model="query"
        :placeholder="searchMode === 'posts' ? 'Search post titles...' : 'Search comment text...'"
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
      {{ searchMode === 'posts' ? 'Search across all scraped posts by title.' : 'Enter at least 2 characters to search across all scraped comments.' }}
    </div>

    <div v-else-if="loading" class="loading">Searching...</div>

    <!-- Post results -->
    <template v-else-if="searchMode === 'posts'">
      <div v-if="!postResults.length" class="empty">
        No posts found for "{{ query }}"
      </div>
      <div v-else>
        <div class="results-count">{{ postResults.length }} results</div>
        <div class="results">
          <RouterLink
            v-for="post in postResults"
            :key="post.id"
            :to="`/posts/${post.id}`"
            class="post-card"
          >
            <div class="post-score" :style="{ color: typeColor(post.post_type) }">
              {{ post.score >= 1000 ? (post.score / 1000).toFixed(1) + "k" : post.score }}
              <span class="vote">▲</span>
            </div>
            <div class="post-body">
              <h3 v-html="highlightMatch(post.title)"></h3>
              <div class="post-meta">
                <span v-if="post.author" class="author">u/{{ post.author }}</span>
                <span>💬 {{ post.num_comments }}</span>
                <span :style="{ color: typeColor(post.post_type) }">{{ post.post_type }}</span>
                <span v-if="post.subreddit">r/{{ post.subreddit.name }}</span>
                <span class="time">{{ timeAgo(post.scraped_at) }}</span>
              </div>
            </div>
          </RouterLink>
        </div>
      </div>
    </template>

    <!-- Comment results -->
    <template v-else>
      <div v-if="!commentResults.length" class="empty">
        No comments found for "{{ query }}"
      </div>
      <div v-else>
        <div class="results-count">{{ commentResults.length }} results</div>
        <div class="results">
          <RouterLink
            v-for="r in commentResults"
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
  </div>
</template>

<style scoped>
h1 { margin-bottom: 1rem; }

.search-bar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  align-items: center;
}

.mode-toggle {
  display: flex;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}

.mode-btn {
  padding: 0.5rem 0.75rem;
  background: var(--bg-card);
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}

.mode-btn.active {
  background: var(--accent);
  color: white;
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

/* Post result cards */
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

.post-body h3 :deep(mark) {
  background: #ff450040;
  color: var(--text);
  border-radius: 2px;
  padding: 0 2px;
}

.post-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}
.author { color: var(--blue); }
.time { margin-left: auto; }

/* Comment result cards */
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

.empty { color: var(--text-muted); text-align: center; padding: 2rem; }
.loading { color: var(--text-muted); }
</style>
