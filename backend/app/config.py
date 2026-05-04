import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./reddit.db")

# --- Reddit OAuth (optional — enables authenticated API requests) ---
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")


class Settings:
    database_url: str = DATABASE_URL

    @property
    def reddit_oauth_enabled(self) -> bool:
        """True when both client_id and client_secret are configured."""
        return bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


settings = Settings()

# --- Scraper defaults (overridable via DB settings) ---

# Max new posts to scrape comments for per run
DEFAULT_MAX_NEW_POSTS = int(os.getenv("MAX_NEW_POSTS", "10"))
# Max top-level comments to keep per post
DEFAULT_TOP_COMMENTS = int(os.getenv("TOP_COMMENTS", "50"))
# Delay between Reddit requests (seconds)
DEFAULT_REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.0"))
# Max comment tree depth
DEFAULT_MAX_COMMENT_DEPTH = int(os.getenv("MAX_COMMENT_DEPTH", "10"))
