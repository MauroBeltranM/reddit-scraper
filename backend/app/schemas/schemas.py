from datetime import datetime

from pydantic import BaseModel


# --- Subreddit ---

class SubredditCreate(BaseModel):
    name: str

class SubredditRead(BaseModel):
    id: int
    name: str
    active: bool
    last_scraped_at: datetime | None = None
    total_posts: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Post ---

class PostRead(BaseModel):
    id: int
    reddit_id: str
    subreddit_id: int
    title: str
    author: str | None = None
    score: int
    upvote_ratio: float | None = None
    num_comments: int
    url: str | None = None
    selftext: str | None = None
    post_type: str = "link"
    permalink: str
    scraped_at: datetime
    subreddit: SubredditRead | None = None

    model_config = {"from_attributes": True}


# --- Comment ---

class CommentRead(BaseModel):
    id: int
    reddit_id: str
    post_id: int
    parent_reddit_id: str | None = None
    author: str | None = None
    score: int
    body: str
    depth: int
    scraped_at: datetime
    replies: list["CommentRead"] = []

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_tree(cls, comment) -> "CommentRead":
        """Build a tree structure from flat comments."""
        node = cls.model_validate(comment)
        node.replies = sorted(
            [cls.from_orm_tree(c) for c in comment.replies if c.parent_reddit_id == comment.reddit_id],
            key=lambda c: c.score,
            reverse=True,
        )
        return node


# --- Snapshot ---

class SnapshotRead(BaseModel):
    id: int
    post_id: int
    score: int
    num_comments: int
    recorded_at: datetime

    model_config = {"from_attributes": True}


# --- Scraping ---

class ScrapeResult(BaseModel):
    subreddit: str
    posts_found: int
    posts_new: int
    comments_total: int
    duration_sec: float


# --- Stats ---

class DashboardStats(BaseModel):
    total_subreddits: int
    total_posts: int
    total_comments: int
    total_snapshots: int
