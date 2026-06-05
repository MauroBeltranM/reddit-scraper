<script setup lang="ts">
import { ref, onMounted } from "vue";
import api from "../api";

interface Settings {
  max_new_posts: number;
  top_comments: number;
  request_delay: number;
  max_comment_depth: number;
}

interface OAuthStatus {
  enabled: boolean;
  connected: boolean;
  has_client_id: boolean;
  has_client_secret: boolean;
}

const settings = ref<Settings>({
  max_new_posts: 10,
  top_comments: 50,
  request_delay: 1.0,
  max_comment_depth: 10,
});
const oauthStatus = ref<OAuthStatus>({
  enabled: false,
  connected: false,
  has_client_id: false,
  has_client_secret: false,
});
const loading = ref(true);
const saving = ref(false);
const saved = ref(false);
const error = ref<string | null>(null);

async function load() {
  try {
    const [settingsData, oauthData] = await Promise.all([
      api.getSettings(),
      api.getOAuthStatus(),
    ]);
    settings.value = settingsData;
    oauthStatus.value = oauthData;
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

    <div v-else>
      <!-- OAuth Section -->
      <div class="section-block">
        <h2 class="section-title">🔐 Reddit OAuth</h2>
        <p class="section-desc">
          Authenticate with Reddit for higher rate limits and access to restricted content.
          Configure via environment variables (<code>REDDIT_CLIENT_ID</code>,
          <code>REDDIT_CLIENT_SECRET</code>).
        </p>

        <div class="oauth-card">
          <div class="oauth-status-row">
            <div class="oauth-status-indicator">
              <span
                class="status-dot"
                :class="oauthStatus.connected ? 'connected' : 'disconnected'"
              ></span>
              <span class="status-text">
                {{ oauthStatus.connected ? "Connected" : oauthStatus.enabled ? "Enabled (not connected)" : "Not configured" }}
              </span>
            </div>
          </div>

          <div class="oauth-fields">
            <div class="oauth-field">
              <label>Client ID</label>
              <div class="field-status">
                <span :class="oauthStatus.has_client_id ? 'ok' : 'missing'">
                  {{ oauthStatus.has_client_id ? "✓ Set" : "✗ Not set" }}
                </span>
              </div>
            </div>
            <div class="oauth-field">
              <label>Client Secret</label>
              <div class="field-status">
                <span :class="oauthStatus.has_client_secret ? 'ok' : 'missing'">
                  {{ oauthStatus.has_client_secret ? "✓ Set" : "✗ Not set" }}
                </span>
              </div>
            </div>
          </div>

          <div v-if="!oauthStatus.enabled" class="oauth-hint">
            To enable OAuth, set both <code>REDDIT_CLIENT_ID</code> and
            <code>REDDIT_CLIENT_SECRET</code> environment variables and restart the app.
          </div>
        </div>
      </div>

      <!-- Scraper Settings -->
      <div class="section-block">
        <h2 class="section-title">🔧 Scraper Settings</h2>

        <div class="settings-form">
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

.section-block {
  margin-bottom: 2rem;
}

.section-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 0.4rem;
}

.section-desc {
  color: var(--text-muted);
  font-size: 0.8rem;
  margin-bottom: 0.75rem;
}

.section-desc code {
  background: var(--bg-card);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  font-size: 0.78rem;
}

/* OAuth card */
.oauth-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  max-width: 600px;
}

.oauth-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.oauth-status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.connected {
  background: var(--green);
  box-shadow: 0 0 6px var(--green);
}

.status-dot.disconnected {
  background: var(--accent);
  box-shadow: 0 0 6px var(--accent);
}

.status-text {
  font-weight: 500;
  font-size: 0.9rem;
}

.oauth-fields {
  display: flex;
  gap: 1.5rem;
  margin-bottom: 0.5rem;
}

.oauth-field {
  flex: 1;
}

.oauth-field label {
  display: block;
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-bottom: 0.2rem;
}

.field-status {
  font-size: 0.85rem;
}

.field-status .ok {
  color: var(--green);
}

.field-status .missing {
  color: var(--accent);
}

.oauth-hint {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: var(--bg-dark);
  border-radius: 6px;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.oauth-hint code {
  background: var(--bg-dark);
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-size: 0.76rem;
  border: 1px solid var(--border);
}

/* Settings form */
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
  color: var(--accent);
  font-size: 0.85rem;
  padding: 0.5rem;
  background: var(--bg-hover);
  border-radius: 6px;
  margin-bottom: 1rem;
}

.loading {
  color: var(--text-muted);
}
</style>
