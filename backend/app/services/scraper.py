import logging
import re
import time
import uuid
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Callable

import httpx
from bs4 import BeautifulSoup

from app.models.models import Comment, Post, Snapshot, Subreddit
from app.schemas.schemas import ScrapeResult
from app.services.reddit_auth import get_reddit_token

logger = logging.getLogger(__name__)

REDDIT_BASE = "https://www.reddit.com"
USER_AGENT = "Mozilla/5.0 (compatible; RedditScraper/0.1)"
REQUEST_DELAY = 1.0  # seconds between requests
MAX_COMMENT_DEPTH = 10
TOP_COMMENTS = 50
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubles each retry

# --- User-friendly error messages in Spanish ---

REDDIT_ERROR_MESSAGES: dict[int, str] = {
    403: "Subreddit restringido o en cuarentena. No se puede acceder al contenido.",
    429: "Demasiadas peticiones a Reddit. Se ha alcanzado el límite de velocidad.",
    500: "Error interno del servidor de Reddit. Inténtalo de nuevo más tarde.",
    502: "Reddit no está disponible temporalmente (bad gateway).",
    503: "Reddit está en mantenimiento. Inténtalo de nuevo más tarde.",
}


def get_reddit_error_message(status_code: int) -> str:
    """Return a user-friendly Spanish error message for a Reddit API status code."""
    return REDDIT_ERROR_MESSAGES.get(
        status_code,
        f"Error de Reddit (HTTP {status_code}). No se pudo completar la solicitud.",
    )


# --- In-memory task progress store ---

class ScrapeTask:
    """Tracks progress of a background scrape task."""
    def __init__(self, task_id: str, subreddit: str):
        self.task_id = task_id
        self.subreddit = subreddit
        self.status: str = "running"  # running | done | error
        self.progress: int = 0
        self.total: int = 0
        self.current_post: str = ""
        self.posts_found: int = 0
        self.posts_new: int = 0
        self.comments_total: int = 0
        self.duration_sec: float = 0.0
        self.error: str = ""
        self.retries_total: int = 0
        self.last_retry_status: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "subreddit": self.subreddit,
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "current_post": self.current_post,
            "posts_found": self.posts_found,
            "posts_new": self.posts_new,
            "comments_total": self.comments_total,
            "duration_sec": self.duration_sec,
            "error": self.error,
            "retries_total": self.retries_total,
            "last_retry_status": self.last_retry_status,
        }


# Global task registry
tasks: dict[str, ScrapeTask] = {}


class RedditScraper:
    def __init__(self, max_new_posts=10, top_comments=50, request_delay=1.0, max_comment_depth=10):
        self.max_new_posts = max_new_posts
        self.top_comments = top_comments
        self.request_delay = request_delay
        self.max_comment_depth = max_comment_depth
        self._current_task: ScrapeTask | None = None
        self._build_client()

    def _build_client(self) -> None:
        """(Re)build the httpx client with current auth headers."""
        headers = {"User-Agent": USER_AGENT}
        token = get_reddit_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
            logger.info("Using Reddit OAuth token for API requests")
        self.client = httpx.Client(
            headers=headers,
            follow_redirects=True,
            timeout=30.0,
        )

    # Status codes that should NOT be retried — immediate failure
    _NO_RETRY_STATUS_CODES = {403}

    # Status codes eligible for retry with backoff
    _RETRY_STATUS_CODES = {429, 500, 502, 503}

    def _request_with_retry(
        self,
        url: str,
        task: ScrapeTask | None = None,
    ) -> httpx.Response | None:
        """Make a GET request with exponential backoff retry on transient errors.

        Handles:
        - 401: Token refresh (once)
        - 403: Immediate failure (forbidden/quarantined)
        - 429/500/502/503: Retry with exponential backoff

        Args:
            url: Full URL to request.
            task: Optional ScrapeTask to update with retry/error info.

        Returns:
            httpx.Response on success, or None if all retries exhausted or non-retryable error.
        """
        for attempt in range(MAX_RETRIES + 1):
            resp = self.client.get(url)

            # Handle 401 — token may have expired
            if resp.status_code == 401 and attempt == 0:
                self._build_client()
                resp = self.client.get(url)

            # Non-retryable errors — fail immediately with user-friendly message
            if resp.status_code in self._NO_RETRY_STATUS_CODES:
                msg = get_reddit_error_message(resp.status_code)
                logger.warning(f"HTTP {resp.status_code} for {url}: {msg}")
                if task:
                    task.error = msg
                return None

            # Retryable errors — backoff and retry
            if resp.status_code in self._RETRY_STATUS_CODES:
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"HTTP {resp.status_code} for {url}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    if task:
                        task.retries_total += 1
                        task.last_retry_status = (
                            f"HTTP {resp.status_code} reintento {attempt + 1}/{MAX_RETRIES}, "
                            f"esperando {delay}s"
                        )
                    time.sleep(delay)
                    continue
                else:
                    msg = get_reddit_error_message(resp.status_code)
                    logger.error(
                        f"HTTP {resp.status_code} exhausted all {MAX_RETRIES} retries for {url}"
                    )
                    if task:
                        task.error = msg
                    return None

            return resp

        return None

    def scrape_subreddit(
        self,
        db,
        subreddit_name: str,
        sort: str = "hot",
        timeframe: str = "all",
        on_progress: Callable[[int, int, str], None] | None = None,
        task: ScrapeTask | None = None,
    ) -> ScrapeResult:
        """Full scrape: discover posts via JSON, then fetch comments for each.

        Args:
            sort: Reddit sort — hot, new, top.
            timeframe: Time window for top sort — hour, day, week, month, year, all.
            on_progress: Optional callback(current, total, post_title) for progress tracking.
            task: Optional ScrapeTask to track retry info.
        """
        start = time.time()

        self._current_task = task

        # Rebuild client to pick up a fresh OAuth token if configured
        self._build_client()

        # Ensure subreddit exists
        subreddit = db.query(Subreddit).filter_by(name=subreddit_name.lower()).first()
        if not subreddit:
            subreddit = Subreddit(name=subreddit_name.lower())
            db.add(subreddit)
            db.flush()

        # Discover posts via JSON
        posts_discovered = self._fetch_posts(subreddit_name, sort=sort, timeframe=timeframe)
        posts_new = 0
        comments_total = 0
        new_count = 0

        for idx, entry in enumerate(posts_discovered):
            # Report progress
            if on_progress:
                on_progress(idx + 1, len(posts_discovered), entry.get("title", "")[:60])

            existing = db.query(Post).filter_by(reddit_id=entry["reddit_id"]).first()
            if existing:
                # Update score/comments and take a new snapshot to track evolution
                existing.score = entry["score"]
                existing.num_comments = entry["num_comments"]
                if entry.get("upvote_ratio"):
                    existing.upvote_ratio = entry["upvote_ratio"]
                db.add(Snapshot(
                    post_id=existing.id,
                    score=existing.score,
                    num_comments=existing.num_comments,
                ))
                continue

            post = Post(
                subreddit_id=subreddit.id,
                reddit_id=entry["reddit_id"],
                title=entry["title"],
                author=entry.get("author"),
                score=entry["score"],
                upvote_ratio=entry.get("upvote_ratio"),
                num_comments=entry["num_comments"],
                url=entry.get("url"),
                selftext=entry.get("selftext"),
                post_type=entry.get("post_type", "link"),
                permalink=entry["permalink"],
                thumbnail_url=entry.get("thumbnail_url"),
                link_flair_text=entry.get("link_flair_text"),
                link_flair_background_color=entry.get("link_flair_background_color"),
            )
            db.add(post)
            db.flush()
            posts_new += 1
            new_count += 1

            # Download thumbnail for image posts
            if entry.get("post_type") == "image":
                # Use the post URL as thumbnail source if Reddit's thumbnail is missing/default
                thumb_url = entry.get("thumbnail_url")
                if not thumb_url or thumb_url in ("self", "default", "nsfw", ""):
                    thumb_url = entry.get("url")  # the image URL itself
                local = self._download_thumbnail(entry["reddit_id"], thumb_url)
                if local:
                    post.local_thumbnail = local
                    db.flush()

            # Fetch comments (limit to avoid long scrapes)
            if new_count <= self.max_new_posts:
                time.sleep(self.request_delay)
            comments = self._fetch_comments(entry["permalink"])
            for c in comments:
                db.add(Comment(
                    post_id=post.id,
                    reddit_id=c["reddit_id"],
                    parent_reddit_id=c.get("parent_reddit_id"),
                    author=c.get("author"),
                    score=c["score"],
                    body=c["body"],
                    depth=c["depth"],
                ))
            comments_total += len(comments)

            # Take initial snapshot
            db.add(Snapshot(post_id=post.id, score=post.score, num_comments=post.num_comments))

        subreddit.last_scraped_at = datetime.now(timezone.utc)
        subreddit.total_posts = db.query(Post).filter_by(subreddit_id=subreddit.id).count()

        return ScrapeResult(
            subreddit=subreddit_name,
            posts_found=len(posts_discovered),
            posts_new=posts_new,
            comments_total=comments_total,
            duration_sec=round(time.time() - start, 2),
        )

    def _fetch_posts(self, subreddit: str, sort: str = "hot", timeframe: str = "all") -> list[dict]:
        """Fetch posts from JSON endpoint.

        Args:
            sort: Reddit sort method (hot, new, top).
            timeframe: Time filter for 'top' sort (hour, day, week, month, year, all).
        """
        url = f"{REDDIT_BASE}/r/{subreddit}/{sort}.json?limit=100"
        if sort == "top" and timeframe:
            url += f"&t={timeframe}"
        try:
            resp = self._request_with_retry(url, task=self._current_task)
            if resp is None:
                # Error already set on task by _request_with_retry if task exists
                logger.warning(f"Failed to fetch posts from /r/{subreddit}")
                return []
            if resp.status_code >= 400:
                msg = get_reddit_error_message(resp.status_code)
                logger.warning(f"HTTP {resp.status_code} fetching posts from /r/{subreddit}: {msg}")
                if self._current_task and not self._current_task.error:
                    self._current_task.error = msg
                return []
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch posts from /r/{subreddit}: {e}")
            return []

        try:
            data = resp.json()
            children = data["data"]["children"]
        except (KeyError, IndexError):
            return []

        posts = []
        for child in children:
            if child["kind"] != "t3":
                continue
            d = child["data"]

            # Determine post type
            post_type = "link"
            if d.get("is_self"):
                post_type = "self"
            elif d.get("is_video"):
                post_type = "video"
            elif d.get("post_hint") == "image":
                post_type = "image"

            posts.append({
                "reddit_id": d["id"],
                "title": d.get("title", ""),
                "author": d.get("author"),
                "score": d.get("score", 0),
                "upvote_ratio": d.get("upvote_ratio"),
                "num_comments": d.get("num_comments", 0),
                "url": d.get("url"),
                "selftext": d.get("selftext", ""),
                "post_type": post_type,
                "permalink": d.get("permalink", ""),
                "thumbnail_url": d.get("thumbnail", None),
                "link_flair_text": d.get("link_flair_text") or None,
                "link_flair_background_color": d.get("link_flair_background_color") or None,
            })

        return posts

    def _fetch_comments(self, permalink: str) -> list[dict]:
        """Fetch comments for a post from its JSON endpoint."""
        url = f"{REDDIT_BASE}{permalink}.json"
        try:
            resp = self._request_with_retry(url, task=self._current_task)
            if resp is None:
                # Error already set on task by _request_with_retry if task exists
                return []
            if resp.status_code >= 400:
                msg = get_reddit_error_message(resp.status_code)
                logger.warning(f"HTTP {resp.status_code} fetching comments for {permalink}: {msg}")
                if self._current_task and not self._current_task.error:
                    self._current_task.error = msg
                return []
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        try:
            data = resp.json()
            if not isinstance(data, list) or len(data) < 2:
                return []
        except Exception:
            return []

        comments_raw = data[1]["data"]["children"]
        all_comments: list[dict] = []

        # Collect top-level, then recursively fetch replies
        queue = [(c["data"], 0) for c in comments_raw if c["kind"] == "t1"]
        # Keep only top N top-level comments
        queue.sort(key=lambda x: x[0].get("score", 0), reverse=True)
        queue = queue[:self.top_comments]

        while queue:
            comment_data, depth = queue.pop(0)
            reddit_id = comment_data["id"]

            all_comments.append({
                "reddit_id": reddit_id,
                "parent_reddit_id": comment_data.get("parent_id"),
                "author": comment_data.get("author"),
                "score": comment_data.get("score", 0),
                "body": self._clean_html(comment_data.get("body", "")),
                "depth": depth,
            })

            if depth < self.max_comment_depth:
                replies = comment_data.get("replies", {})
                if isinstance(replies, dict):
                    for reply in replies.get("data", {}).get("children", []):
                        if reply["kind"] == "t1":
                            queue.append((reply["data"], depth + 1))

        return all_comments

    @staticmethod
    def _clean_html(text: str) -> str:
        if not text:
            return ""
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all("a"):
            href = a.get("href", "")
            link_text = a.get_text()
            a.replace_with(f"[{link_text}]({href})")
        return soup.get_text("\n", strip=True)

    @staticmethod
    def _get_thumbnail_dir() -> Path:
        """Return the thumbnails directory, creating it if needed."""
        thumb_dir = Path("/app/data/thumbnails")
        thumb_dir.mkdir(parents=True, exist_ok=True)
        return thumb_dir

    def _download_thumbnail(self, reddit_id: str, thumbnail_url: str) -> str | None:
        """Download a thumbnail image and return the local filename, or None on failure."""
        if not thumbnail_url or thumbnail_url in ("self", "default", "nsfw", "", None):
            return None
        try:
            resp = self.client.get(thumbnail_url)
            resp.raise_for_status()
            filename = f"{reddit_id}.jpg"
            path = self._get_thumbnail_dir() / filename
            path.write_bytes(resp.content)
            return filename
        except Exception as e:
            logger.warning(f"Failed to download thumbnail for {reddit_id}: {e}")
            return None

    def close(self):
        self.client.close()
