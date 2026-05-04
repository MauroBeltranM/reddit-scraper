"""Reddit OAuth2 service — obtains and caches an access token via client_credentials grant.

Usage:
    from app.services.reddit_auth import get_reddit_token

    token = get_reddit_token()  # str | None
    if token:
        headers["Authorization"] = f"Bearer {token}"
"""

import logging
import time
import threading

import httpx

from app.config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, settings

logger = logging.getLogger(__name__)

# Reddit token endpoint
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"

# Cached token state (protected by lock)
_lock = threading.Lock()
_cached_token: str | None = None
_expires_at: float = 0.0  # epoch seconds


def _request_token() -> tuple[str, float] | None:
    """Request a new access token from Reddit. Returns (token, expires_at) or None."""
    if not settings.reddit_oauth_enabled:
        return None

    try:
        resp = httpx.post(
            TOKEN_URL,
            auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
            data={
                "grant_type": "client_credentials",
                "device_id": "reddit-scraper-app",  # stable device id
            },
            headers={
                "User-Agent": "RedditScraper/0.1 (by /u/reddit_scraper)",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        access_token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)

        if not access_token:
            logger.warning("Reddit OAuth response missing access_token")
            return None

        # Convert to absolute expiration, with 60s safety margin
        expires_at = time.time() + expires_in - 60
        logger.info(f"Reddit OAuth token obtained, expires in {expires_in}s")
        return access_token, expires_at

    except httpx.HTTPError as e:
        logger.warning(f"Failed to obtain Reddit OAuth token: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error obtaining Reddit OAuth token: {e}")
        return None


def get_reddit_token() -> str | None:
    """Return a cached Reddit access token, refreshing if needed.

    Returns None if OAuth is not configured or if token retrieval fails.
    Thread-safe.
    """
    global _cached_token, _expires_at

    if not settings.reddit_oauth_enabled:
        return None

    with _lock:
        now = time.time()
        if _cached_token and _expires_at > now:
            return _cached_token

        result = _request_token()
        if result is None:
            # Return stale token if we have one, else None
            return _cached_token

        _cached_token, _expires_at = result
        return _cached_token


def invalidate_token() -> None:
    """Force a token refresh on next get_reddit_token() call."""
    global _cached_token, _expires_at
    with _lock:
        _cached_token = None
        _expires_at = 0.0
