import re
import time
import uuid
from datetime import datetime, timezone
from html import unescape
from typing import Callable

import httpx
from bs4 import BeautifulSoup

from app.models.models import Comment, Post, Snapshot, Subreddit
from app.schemas.schemas import ScrapeResult

REDDIT_BASE = "https://www.reddit.com"
USER_AGENT = "Mozilla/5.0 (compatible; RedditScraper/0.1)"
REQUEST_DELAY = 1.0  # seconds between requests
MAX_COMMENT_DEPTH = 10
TOP_COMMENTS = 50


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
        }


# Global task registry
tasks: dict[str, ScrapeTask] = {}


class RedditScraper:
    def __init__(self, max_new_posts=10, top_comments=50, request_delay=1.0, max_comment_depth=10):
        self.max_new_posts = max_new_posts
        self.top_comments = top_comments
        self.request_delay = request_delay
        self.max_comment_depth = max_comment_depth
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        )

    def scrape_subreddit(
        self,
        db,
        subreddit_name: str,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> ScrapeResult:
        """Full scrape: discover posts via JSON, then fetch comments for each.

        Args:
            on_progress: Optional callback(current, total, post_title) for progress tracking.
        """
        start = time.time()

        # Ensure subreddit exists
        subreddit = db.query(Subreddit).filter_by(name=subreddit_name.lower()).first()
        if not subreddit:
            subreddit = Subreddit(name=subreddit_name.lower())
            db.add(subreddit)
            db.flush()

        # Discover posts via JSON
        posts_discovered = self._fetch_posts(subreddit_name)
        posts_new = 0
        comments_total = 0
        new_count = 0

        for idx, entry in enumerate(posts_discovered):
            # Report progress
            if on_progress:
                on_progress(idx + 1, len(posts_discovered), entry.get("title", "")[:60])

            existing = db.query(Post).filter_by(reddit_id=entry["reddit_id"]).first()
            if existing:
                # Update score/comments
                existing.score = entry["score"]
                existing.num_comments = entry["num_comments"]
                if entry.get("upvote_ratio"):
                    existing.upvote_ratio = entry["upvote_ratio"]
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
            )
            db.add(post)
            db.flush()
            posts_new += 1
            new_count += 1

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

    def _fetch_posts(self, subreddit: str) -> list[dict]:
        """Fetch posts from JSON endpoint."""
        url = f"{REDDIT_BASE}/r/{subreddit}/top.json?t=all&limit=100"
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
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
            })

        return posts

    def _fetch_comments(self, permalink: str) -> list[dict]:
        """Fetch comments for a post from its JSON endpoint."""
        url = f"{REDDIT_BASE}{permalink}.json"
        try:
            resp = self.client.get(url)
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

    def close(self):
        self.client.close()
