<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, RouterLink } from "vue-router";
import api from "../api";

interface Comment {
  id: number;
  reddit_id: string;
  author: string | null;
  score: number;
  body: string;
  depth: number;
  replies: Comment[];
}

interface Snapshot {
  score: number;
  num_comments: number;
  recorded_at: string;
}

const route = useRoute();
const post = ref<any>(null);
const comments = ref<Comment[]>([]);
const snapshots = ref<Snapshot[]>([]);
const loading = ref(true);
const commentsPage = ref(0);
const commentsHasMore = ref(true);
const commentsLoading = ref(false);
const totalRoots = ref(0);
const commentsPageSize = 20;

function formatBody(text: string) {
  // Basic markdown: links, bold, italic
  return text
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br>");
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function formatSnapDate(d: string) {
  return new Date(d).toLocaleString();
}

async function loadMoreComments() {
  commentsLoading.value = true;
  const id = Number(route.params.id);
  const data = await api.getPostComments(id, commentsPageSize, commentsPage.value * commentsPageSize);
  comments.value.push(...(data.comments || []));
  totalRoots.value = data.total_roots || 0;
  commentsHasMore.value = comments.value.length < data.total_roots;
  commentsPage.value++;
  commentsLoading.value = false;
}

onMounted(async () => {
  const id = Number(route.params.id);
  const [postData, snapData] = await Promise.all([
    api.getPost(id),
    api.getPostSnapshots(id),
  ]);
  post.value = postData;
  snapshots.value = snapData;
  loading.value = false;
  // Load first batch of comments
  await loadMoreComments();
});
</script>

<template>
  <div class="post-detail" v-if="!loading && post">
    <RouterLink to="/posts" class="back">← Back to posts</RouterLink>

    <div class="post-header">
      <h1 class="post-title">{{ post.title }}</h1>
      <div class="post-meta">
        <span :class="['type-badge', post.post_type]">{{ post.post_type }}</span>
        <span v-if="post.subreddit" class="sub">r/{{ post.subreddit.name }}</span>
        <span v-if="post.author" class="author">by u/{{ post.author }}</span>
        <span> {{ post.score.toLocaleString() }} ▲</span>
        <span>💬 {{ post.num_comments }}</span>
        <a :href="'https://reddit.com' + post.permalink" target="_blank" class="reddit-link">
          Open on Reddit ↗
        </a>
      </div>
    </div>

    <div v-if="post.selftext" class="selftext" v-html="formatBody(post.selftext)"></div>

    <div class="snapshots" v-if="snapshots.length > 1">
      <h3>📊 Score History</h3>
      <div class="snap-chart">
        <div
          v-for="(snap, i) in snapshots"
          :key="i"
          class="snap-bar"
          :style="{ height: (snap.score / Math.max(...snapshots.map(s => s.score)) * 100) + '%' }"
          :title="`${snap.score} points · ${snap.num_comments} comments · ${formatSnapDate(snap.recorded_at)}`"
        />
      </div>
      <div class="snap-legend">
        {{ snapshots.length }} snapshots ·
        {{ snapshots[0].score }} → {{ snapshots[snapshots.length - 1].score }} points
      </div>
    </div>

    <div class="comments-section">
      <h2>Comments ({{ totalRoots }} threads, {{ comments.length }} loaded)</h2>
      <CommentTree :comments="comments" :format-body="formatBody" :time-ago="timeAgo" />
      <button
        v-if="commentsHasMore && comments.length > 0"
        class="load-more-comments"
        :disabled="commentsLoading"
        @click="loadMoreComments"
      >
        {{ commentsLoading ? "Loading..." : "Load more comments" }}
      </button>
      <div v-if="comments.length === 0 && !loading" class="empty-comments">No comments yet.</div>
    </div>
  </div>

  <div v-else class="loading">Loading...</div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from "vue";

const CommentTree = defineComponent({
  name: "CommentTree",
  props: {
    comments: { type: Array as PropType<any[]>, required: true },
    formatBody: { type: Function, required: true },
    timeAgo: { type: Function, required: true },
  },
  setup(props) {
    return { comments: props.comments, formatBody: props.formatBody, timeAgo: props.timeAgo };
  },
  template: `
    <div class="comment-tree">
      <div v-for="c in comments" :key="c.reddit_id" class="comment" :style="{ marginLeft: c.depth * 24 + 'px' }">
        <div class="comment-header">
          <span class="comment-score">{{ c.score }} ▲</span>
          <span v-if="c.author" class="comment-author">u/{{ c.author }}</span>
          <span v-else class="comment-author deleted">[deleted]</span>
        </div>
        <div class="comment-body" v-html="formatBody(c.body)"></div>
        <CommentTree v-if="c.replies?.length" :comments="c.replies" :format-body="formatBody" :time-ago="timeAgo" />
      </div>
    </div>
  `,
});

export default { components: { CommentTree } };
</script>

<style scoped>
.back {
  color: var(--text-muted);
  font-size: 0.85rem;
  display: inline-block;
  margin-bottom: 1rem;
}

.back:hover { color: var(--text); }

.post-header { margin-bottom: 1.5rem; }

.post-title {
  font-size: 1.3rem;
  line-height: 1.4;
  margin-bottom: 0.5rem;
}

.post-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  flex-wrap: wrap;
}

.type-badge {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  background: var(--bg-hover);
}

.type-badge.self { color: #3fb950; }
.type-badge.link { color: #58a6ff; }
.type-badge.image { color: #bc8cff; }

.sub { color: var(--accent); font-weight: 500; }
.author { color: var(--blue); }

.reddit-link {
  color: var(--blue);
  font-weight: 500;
}

.selftext {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
  line-height: 1.6;
}

.snapshots {
  margin-bottom: 2rem;
}

.snapshots h3 {
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
  color: var(--text-muted);
}

.snap-chart {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 60px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.5rem;
}

.snap-bar {
  flex: 1;
  background: var(--accent);
  border-radius: 2px 2px 0 0;
  min-height: 2px;
  transition: height 0.3s;
}

.snap-legend {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.3rem;
}

.comments-section h2 {
  font-size: 1.1rem;
  margin-bottom: 1rem;
}

.comment {
  padding: 0.5rem 0;
  border-left: 2px solid var(--border);
  padding-left: 0.75rem;
  margin-bottom: 0.25rem;
}

.comment:hover { border-left-color: var(--accent); }

.comment-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.2rem;
}

.comment-score {
  font-weight: 600;
  font-size: 0.8rem;
  color: var(--accent);
}

.comment-author {
  font-size: 0.8rem;
  color: var(--blue);
}

.comment-author.deleted { color: var(--text-muted); font-style: italic; }

.comment-body {
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--text);
  overflow-wrap: break-word;
}

.comment-body :deep(a) {
  color: var(--blue);
}

.loading { color: var(--text-muted); }

.load-more-comments {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  cursor: pointer;
  display: block;
  width: 100%;
  text-align: center;
}
.load-more-comments:hover { background: var(--bg-hover); }
.load-more-comments:disabled { opacity: 0.5; cursor: not-allowed; }

.empty-comments { color: var(--text-muted); text-align: center; padding: 2rem; }
</style>
