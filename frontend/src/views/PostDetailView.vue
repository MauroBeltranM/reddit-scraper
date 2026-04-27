<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import api from "../api";

const route = useRoute();
const post = ref<any>(null);
const comments = ref<any[]>([]);
const snapshots = ref<any[]>([]);
const loading = ref(true);

onMounted(load);

async function load() {
  const id = Number(route.params.id);
  post.value = await api.getPost(id);
  comments.value = await api.getPostComments(id);
  snapshots.value = await api.getPostSnapshots(id);
  loading.value = false;
}

function redditUrl() {
  if (!post.value) return "#";
  return `https://reddit.com${post.value.permalink}`;
}

function formatSnapshots() {
  if (snapshots.value.length < 2) return null;
  const first = snapshots.value[0];
  const last = snapshots.value[snapshots.value.length - 1];
  const scoreDiff = last.score - first.score;
  const commentDiff = last.num_comments - first.num_comments;
  return { scoreDiff, commentDiff, count: snapshots.value.length };
}
</script>

<template>
  <div class="post-detail" v-if="!loading && post">
    <router-link to="/posts" class="back">← Back to posts</router-link>

    <div class="post-card">
      <div class="post-header">
        <h1>{{ post.title }}</h1>
        <div class="post-meta">
          <span v-if="post.author" class="author">u/{{ post.author }}</span>
          <span>/r/{{ post.subreddit?.name }}</span>
          <span class="type-badge">{{ post.post_type }}</span>
        </div>
        <div class="post-stats">
          <span class="stat">▲ {{ post.score }}</span>
          <span class="stat">💬 {{ post.num_comments }}</span>
          <span v-if="post.upvote_ratio" class="stat">⚡ {{ (post.upvote_ratio * 100).toFixed(0) }}%</span>
          <a :href="redditUrl()" target="_blank" class="stat link">Open on Reddit →</a>
        </div>
      </div>

      <div v-if="post.selftext" class="selftext">{{ post.selftext }}</div>

      <div v-if="formatSnapshots()" class="trend">
        <span :class="formatSnapshots()!.scoreDiff >= 0 ? 'trend-up' : 'trend-down'">
          {{ formatSnapshots()!.scoreDiff >= 0 ? "↑" : "↓" }} {{ Math.abs(formatSnapshots()!.scoreDiff) }} score
        </span>
        <span :class="formatSnapshots()!.commentDiff >= 0 ? 'trend-up' : 'trend-down'">
          {{ formatSnapshots()!.commentDiff >= 0 ? "↑" : "↓" }} {{ Math.abs(formatSnapshots()!.commentDiff) }} comments
        </span>
        <span class="trend-meta">({{ formatSnapshots()!.count }} snapshots)</span>
      </div>
    </div>

    <h2 class="comments-title">Comments ({{ comments.length }} threads)</h2>

    <div class="comments">
      <CommentThread v-for="c in comments" :key="c.id" :comment="c" :depth="0" />
    </div>

    <div v-if="comments.length === 0" class="empty">No comments scraped yet.</div>
  </div>

  <div v-else class="loading">Loading...</div>
</template>

<script lang="ts">
import { defineComponent } from "vue";

const CommentThread = defineComponent({
  name: "CommentThread",
  props: { comment: Object, depth: { type: Number, default: 0 } },
  setup(props) {
    function scoreColor(score: number) {
      if (score >= 100) return "#ff4500";
      if (score >= 10) return "#ffd700";
      return "var(--text-muted)";
    }
    return { scoreColor, comment: props.comment, depth: props.depth };
  },
  template: `
    <div class="comment" :style="{ marginLeft: depth * 16 + 'px' }">
      <div class="comment-header">
        <span v-if="comment.author" class="comment-author">u/{{ comment.author }}</span>
        <span v-else class="comment-author deleted">[deleted]</span>
        <span class="comment-score" :style="{ color: scoreColor(comment.score) }">
          {{ comment.score }} ▲
        </span>
      </div>
      <div class="comment-body">{{ comment.body }}</div>
      <div v-if="comment.replies && comment.replies.length" class="comment-replies">
        <CommentThread
          v-for="reply in comment.replies.slice(0, 10)"
          :key="reply.id"
          :comment="reply"
          :depth="depth + 1"
        />
        <div v-if="comment.replies.length > 10" class="more-replies">
          +{{ comment.replies.length - 10 }} more replies
        </div>
      </div>
    </div>
  `,
});

export default { components: { CommentThread } };
</script>

<style scoped>
.back {
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-bottom: 1rem;
  display: inline-block;
}
.back:hover { color: var(--text); }

.post-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.post-header h1 { font-size: 1.25rem; margin-bottom: 0.5rem; line-height: 1.3; }

.post-meta {
  display: flex;
  gap: 0.75rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.author { color: var(--blue); }
.type-badge {
  background: var(--bg-hover);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-size: 0.7rem;
}

.post-stats { display: flex; gap: 1rem; font-size: 0.85rem; }
.stat { color: var(--text-muted); }
.stat.link { color: var(--blue); }

.selftext {
  margin-top: 1rem;
  padding: 1rem;
  background: var(--bg-dark);
  border-radius: 6px;
  font-size: 0.85rem;
  line-height: 1.5;
  white-space: pre-wrap;
  color: var(--text-muted);
  max-height: 200px;
  overflow-y: auto;
}

.trend {
  margin-top: 1rem;
  display: flex;
  gap: 1rem;
  font-size: 0.8rem;
}

.trend-up { color: var(--green); font-weight: 600; }
.trend-down { color: #f85149; font-weight: 600; }
.trend-meta { color: var(--text-muted); }

.comments-title { font-size: 1.1rem; margin-bottom: 1rem; }
.empty { color: var(--text-muted); text-align: center; padding: 2rem; }
.loading { color: var(--text-muted); }
</style>

<style>
.comment {
  padding: 0.5rem 0;
  border-left: 2px solid var(--border);
  margin-left: 8px;
  padding-left: 12px;
}

.comment-header {
  display: flex;
  gap: 0.5rem;
  font-size: 0.75rem;
  margin-bottom: 0.25rem;
}

.comment-author { color: var(--blue); }
.comment-author.deleted { color: var(--text-muted); font-style: italic; }
.comment-score { font-weight: 600; }

.comment-body {
  font-size: 0.8rem;
  line-height: 1.4;
  color: var(--text);
  margin-bottom: 0.25rem;
}

.comment-replies { margin-top: 0.25rem; }

.more-replies {
  font-size: 0.75rem;
  color: var(--text-muted);
  padding: 0.25rem 0;
}
</style>
