<script setup lang="ts">
import { ref, onMounted } from "vue";
import api from "../api";

interface Settings {
  max_new_posts: number;
  top_comments: number;
  request_delay: number;
  max_comment_depth: number;
}

const settings = ref<Settings>({
  max_new_posts: 10,
  top_comments: 50,
  request_delay: 1.0,
  max_comment_depth: 10,
});
const loading = ref(true);
const saving = ref(false);
const saved = ref(false);
const error = ref<string | null>(null);

async function load() {
  try {
    settings.value = await api.getSettings();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  saved.value = false;
  error.value = null;
  try {
    settings.value = await api.updateSettings(settings.value);
    saved.value = true;
    setTimeout(() => (saved.value = false), 3000);
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message;
  } finally {
    saving.value = false;
  }
}

const fields = [
  {
    key: "max_new_posts" as const,
    label: "Max new posts per scrape",
    description: "How many new posts to fetch comments for in each scrape run.",
    min: 1,
    max: 100,
    step: 1,
  },
  {
    key: "top_comments" as const,
    label: "Top comments per post",
    description: "Number of top-level comments to keep for each post.",
    min: 5,
    max: 200,
    step: 5,
  },
  {
    key: "request_delay" as const,
    label: "Request delay (seconds)",
    description: "Pause between Reddit requests to avoid rate limiting.",
    min: 0.2,
    max: 10,
    step: 0.1,
  },
  {
    key: "max_comment_depth" as const,
    label: "Max comment depth",
    description: "How deep to recurse into comment reply trees.",
    min: 1,
    max: 50,
    step: 1,
  },
];

onMounted(load);
</script>

<template>
  <div class="settings-view">
    <h1>⚙️ Settings</h1>
    <p class="subtitle">Configure scraping behavior. Changes apply to the next scrape.</p>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else class="settings-form">
      <div v-for="field in fields" :key="field.key" class="setting-row">
        <div class="setting-info">
          <label :for="field.key">{{ field.label }}</label>
          <span class="setting-desc">{{ field.description }}</span>
        </div>
        <div class="setting-input">
          <input
            :id="field.key"
            v-model.number="settings[field.key]"
            type="number"
            :min="field.min"
            :max="field.max"
            :step="field.step"
            class="input"
          />
        </div>
      </div>

      <div v-if="error" class="error-msg">{{ error }}</div>

      <button @click="save" :disabled="saving" class="btn btn-accent">
        {{ saving ? "Saving..." : saved ? "✓ Saved" : "Save Settings" }}
      </button>
    </div>
  </div>
</template>

<style scoped>
h1 {
  margin-bottom: 0.25rem;
}

.subtitle {
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-bottom: 1.5rem;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 600px;
}

.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.75rem 1rem;
}

.setting-info {
  flex: 1;
  margin-right: 1rem;
}

.setting-info label {
  display: block;
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 0.2rem;
}

.setting-desc {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.setting-input {
  flex-shrink: 0;
}

.input {
  width: 90px;
  padding: 0.4rem 0.5rem;
  background: var(--bg-dark);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 0.9rem;
  text-align: right;
}

.input:focus {
  outline: none;
  border-color: var(--accent);
}

.btn {
  padding: 0.6rem 1.5rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.15s;
  align-self: flex-start;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-accent {
  background: var(--accent);
  color: white;
}

.btn-accent:hover:not(:disabled) {
  background: var(--accent-hover);
}

.error-msg {
  color: #f85149;
  font-size: 0.85rem;
  padding: 0.5rem;
  background: #f8514915;
  border-radius: 6px;
}

.loading {
  color: var(--text-muted);
}
</style>
