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

  // Posts
  getPosts: (params?: Record<string, string | number>) =>
    api.get("/posts", { params }).then((r) => r.data),
  getPost: (id: number) => api.get(`/posts/${id}`).then((r) => r.data),
  getPostComments: (id: number) => api.get(`/posts/${id}/comments`).then((r) => r.data),
  getPostSnapshots: (id: number) => api.get(`/posts/${id}/snapshots`).then((r) => r.data),

  // Search
  searchComments: (q: string, subredditId?: number) =>
    api.get("/comments/search", { params: { q, subreddit_id: subredditId } }).then((r) => r.data),

  // Stats
  getStats: () => api.get("/stats").then((r) => r.data),
};
