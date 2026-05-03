<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
import api from "../api";
import {
  Chart,
  BarController,
  BarElement,
  LineController,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Legend,
  Title,
  Filler,
} from "chart.js";

Chart.register(
  BarController,
  BarElement,
  LineController,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Legend,
  Title,
  Filler,
);

const stats = ref({ total_subreddits: 0, total_posts: 0, total_comments: 0, total_snapshots: 0 });
const loading = ref(true);
const chartsError = ref<string | null>(null);

// Chart instances are managed by Chart.js internally — no need to track them
// since the canvas elements keep them alive for the component's lifetime.

const defaultChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: "#161b22",
      borderColor: "#30363d",
      borderWidth: 1,
      titleColor: "#e6edf3",
      bodyColor: "#8b949e",
      padding: 10,
      cornerRadius: 6,
    },
  },
  scales: {
    x: {
      ticks: { color: "#8b949e", maxRotation: 45 },
      grid: { color: "#30363d44" },
      border: { color: "#30363d" },
    },
    y: {
      ticks: { color: "#8b949e" },
      grid: { color: "#30363d44" },
      border: { color: "#30363d" },
    },
  },
};

function buildCharts(data: {
  posts_by_subreddit: { subreddit_name: string; post_count: number }[];
  top_posts: { title: string; score: number; subreddit_name: string }[];
  timeline: { date: string; post_count: number }[];
}) {
  // 1) Posts by subreddit — horizontal bar
  const subLabels = data.posts_by_subreddit.map((s) => `r/${s.subreddit_name}`);
  const subCounts = data.posts_by_subreddit.map((s) => s.post_count);

  new Chart(document.getElementById("postsBySubChart") as HTMLCanvasElement, {
    type: "bar",
    data: {
      labels: subLabels,
      datasets: [
        {
          label: "Posts",
          data: subCounts,
          backgroundColor: "#ff450088",
          borderColor: "#ff4500",
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    },
    options: {
      ...defaultChartOptions,
      indexAxis: "y",
      plugins: {
        ...defaultChartOptions.plugins,
        title: { display: false },
      },
    },
  });

  // 2) Top 10 posts by score — vertical bar
  const topLabels = data.top_posts.map((p) =>
    p.title.length > 40 ? p.title.slice(0, 37) + "…" : p.title,
  );
  const topScores = data.top_posts.map((p) => p.score);

  new Chart(document.getElementById("topPostsChart") as HTMLCanvasElement, {
    type: "bar",
    data: {
      labels: topLabels,
      datasets: [
        {
          label: "Score",
          data: topScores,
          backgroundColor: "#58a6ff88",
          borderColor: "#58a6ff",
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    },
    options: {
      ...defaultChartOptions,
      plugins: {
        ...defaultChartOptions.plugins,
        tooltip: {
          ...defaultChartOptions.plugins.tooltip,
          callbacks: {
            title: (items) => {
              const idx = items[0].dataIndex;
              return data.top_posts[idx].title;
            },
            afterTitle: (items) => {
              const idx = items[0].dataIndex;
              return `r/${data.top_posts[idx].subreddit_name}`;
            },
          },
        },
      },
    },
  });

  // 3) Timeline — line chart with fill
  const tlLabels = data.timeline.map((t) => t.date);
  const tlCounts = data.timeline.map((t) => t.post_count);

  new Chart(document.getElementById("timelineChart") as HTMLCanvasElement, {
    type: "line",
    data: {
      labels: tlLabels,
      datasets: [
        {
          label: "Posts scraped",
          data: tlCounts,
          borderColor: "#3fb950",
          backgroundColor: "#3fb95022",
          fill: true,
          tension: 0.3,
          pointRadius: 3,
          pointBackgroundColor: "#3fb950",
        },
      ],
    },
    options: {
      ...defaultChartOptions,
      plugins: {
        ...defaultChartOptions.plugins,
      },
      scales: {
        ...defaultChartOptions.scales,
        x: {
          ...defaultChartOptions.scales.x,
          ticks: {
            ...defaultChartOptions.scales.x.ticks,
            maxTicksLimit: 15,
          },
        },
      },
    },
  });
}

onMounted(async () => {
  try {
    const [statsData, chartData] = await Promise.all([api.getStats(), api.getChartData()]);
    stats.value = statsData;
    loading.value = false;

    await nextTick();
    buildCharts(chartData);
  } catch (e: any) {
    loading.value = false;
    chartsError.value = e?.message || "Failed to load chart data";
  }
});
</script>

<template>
  <div class="dashboard">
    <h1>Dashboard</h1>

    <div v-if="loading" class="loading">Loading...</div>

    <template v-else>
      <!-- Stats cards -->
      <div class="stats-grid">
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

      <!-- Charts -->
      <div v-if="chartsError" class="charts-error">⚠️ {{ chartsError }}</div>

      <div class="charts-grid">
        <div class="chart-card">
          <h2 class="chart-title">Posts by Subreddit</h2>
          <div class="chart-container chart-container--wide">
            <canvas id="postsBySubChart"></canvas>
          </div>
        </div>

        <div class="chart-card">
          <h2 class="chart-title">Top 10 Posts by Score</h2>
          <div class="chart-container">
            <canvas id="topPostsChart"></canvas>
          </div>
        </div>

        <div class="chart-card">
          <h2 class="chart-title">Scraping Timeline (Last 30 Days)</h2>
          <div class="chart-container">
            <canvas id="timelineChart"></canvas>
          </div>
        </div>
      </div>
    </template>
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
  margin-bottom: 2rem;
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

/* Charts */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

.chart-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.25rem;
}

/* Posts by subreddit spans full width on the first row */
.chart-card:first-child {
  grid-column: 1 / -1;
}

.chart-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.chart-container {
  position: relative;
  height: 300px;
}

.chart-container--wide {
  height: 350px;
}

.charts-error {
  background: #3d1f1f;
  border: 1px solid #6e3030;
  color: #f07070;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

@media (max-width: 768px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
