import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
});

export default {
  // Subreddits
  getSubreddits: () => api.get("/subreddits").then((r) => r.data),
  addSubreddit: (name: string) => api.post("/subreddits", { name }),
  removeSubreddit: (id: number) => api.delete(`/subreddits/${id}`),

  // Scraping
  scrape: (name: string) => api.post(`/scrape/${name}`).then((r) => r.data),
  scrapeAll: () => api.post("/scrape-all").then((r) => r.data),

  /** Subscribe to SSE progress events for a subreddit scrape */
  scrapeProgress: (name: string): EventSource => {
    const base = api.defaults.baseURL || "/api";
    return new EventSource(`${base}/scrape/${name}/progress`);
  },

  // Posts
  getPosts: (params?: Record<string, string | number>) =>
    api.get("/posts", { params }).then((r) => r.data),
  getPost: (id: number) => api.get(`/posts/${id}`).then((r) => r.data),
  getPostComments: (id: number, limit = 20, offset = 0) =>
    api.get(`/posts/${id}/comments`, { params: { limit, offset } }).then((r) => r.data),
  getPostSnapshots: (id: number) => api.get(`/posts/${id}/snapshots`).then((r) => r.data),

  // Search
  searchComments: (q: string, subredditId?: number) =>
    api.get("/comments/search", { params: { q, subreddit_id: subredditId } }).then((r) => r.data),

  // Stats
  getStats: () => api.get("/stats").then((r) => r.data),

  // Settings
  getSettings: () => api.get("/settings").then((r) => r.data),
  updateSettings: (data: Record<string, number>) => api.put("/settings", data).then((r) => r.data),
};
