import re
import time
from datetime import datetime, timezone
from html import unescape

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.models.models import Comment, Post, Subreddit, Snapshot
from app.schemas.schemas import ScrapeResult

REDDIT_BASE = "https://www.reddit.com"
USER_AGENT = "Mozilla/5.0 (compatible; RedditScraper/0.1)"
REQUEST_DELAY = 1.0
MAX_COMMENT_DEPTH = 10
TOP_COMMENTS = 50


class RedditScraper:
    def __init__(self):
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        )

    def scrape_subreddit(self, db, subreddit_name: str) -> ScrapeResult:
        start = time.time()

        subreddit = db.query(Subreddit).filter_by(name=subreddit_name.lower()).first()
        if not subreddit:
            subreddit = Subreddit(name=subreddit_name.lower())
            db.add(subreddit)
            db.flush()

        posts_discovered = self._fetch_rss(subreddit_name)
        posts_new = 0
        comments_total = 0

        for entry in posts_discovered:
            existing = db.query(Post).filter_by(reddit_id=entry["reddit_id"]).first()
            if existing:
                existing.score = entry["score"]
                existing.num_comments = entry["num_comments"]
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

            time.sleep(REQUEST_DELAY)
            comments = self._fetch_comments(post.permalink)
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

    def _fetch_rss(self, subreddit: str) -> list[dict]:
        url = f"{REDDIT_BASE}/r/{subreddit}/hot/.rss?limit=100"
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        feed = feedparser.parse(resp.text)
        posts = []

        for entry in feed.entries:
            reddit_id = self._extract_reddit_id(entry.get("id", ""))
            if not reddit_id:
                continue

            post_type = "link"
            if entry.get("media_content"):
                post_type = "image"
            elif entry.get("link", "").startswith(REDDIT_BASE):
                post_type = "self"

            posts.append({
                "reddit_id": reddit_id,
                "title": unescape(entry.get("title", "")),
                "author": self._clean_author(entry.get("author", "")),
                "score": int(entry.get("threddit_score", 0) or 0),
                "num_comments": int(entry.get("threddit_num_comments", 0) or 0),
                "url": entry.get("link"),
                "selftext": entry.get("summary_detail", {}).get("value"),
                "post_type": post_type,
                "permalink": entry.get("id", "").replace(f"https://www.reddit.com", ""),
            })

        return posts

    def _fetch_comments(self, permalink: str) -> list[dict]:
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

        queue = [(c["data"], 0) for c in comments_raw if c["kind"] == "t1"]
        queue.sort(key=lambda x: x[0].get("score", 0), reverse=True)
        queue = queue[:TOP_COMMENTS]

        while queue:
            comment_data, depth = queue.pop(0)
            reddit_id = comment_data["id"]

            all_comments.append({
                "reddit_id": reddit_id,
                "parent_reddit_id": comment_data.get("parent_id"),
                "author": self._clean_author(comment_data.get("author", "")),
                "score": comment_data.get("score", 0),
                "body": self._clean_html(comment_data.get("body", "")),
                "depth": depth,
            })

            if depth < MAX_COMMENT_DEPTH:
                replies = comment_data.get("replies", {})
                if isinstance(replies, dict):
                    for reply in replies.get("data", {}).get("children", []):
                        if reply["kind"] == "t1":
                            queue.append((reply["data"], depth + 1))

        return all_comments

    @staticmethod
    def _extract_reddit_id(entry_id: str) -> str:
        match = re.search(r"/comments/([a-z0-9]+)/", entry_id)
        return match.group(1) if match else ""

    @staticmethod
    def _clean_author(author: str) -> str | None:
        if not author or author.startswith("/u/"):
            return None
        clean = re.sub(r"\s*\(.*\)", "", author).strip()
        return clean if clean and clean != "[deleted]" else None

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
