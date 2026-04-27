<script setup lang="ts">
import { ref, onMounted } from "vue";
import api from "../api";

const stats = ref({ total_subreddits: 0, total_posts: 0, total_comments: 0, total_snapshots: 0 });
const loading = ref(true);

onMounted(async () => {
  stats.value = await api.getStats();
  loading.value = false;
});
</script>

<template>
  <div class="dashboard">
    <h1>Dashboard</h1>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else class="stats-grid">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total_subreddits }}</div>
        <div class="stat-label">Subreddits</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.total_posts }}</div>
        <div class="stat-label">Posts</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.total_comments.toLocaleString() }}</div>
        <div class="stat-label">Comments</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.total_snapshots.toLocaleString() }}</div>
        <div class="stat-label">Snapshots</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
h1 {
  font-size: 1.5rem;
  margin-bottom: 1.5rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.5rem;
  text-align: center;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--accent);
}

.stat-label {
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-top: 0.25rem;
}

.loading {
  color: var(--text-muted);
}
</style>
