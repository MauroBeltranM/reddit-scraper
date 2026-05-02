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


# --- Chart Data ---


class PostsBySubreddit(BaseModel):
    subreddit_id: int
    subreddit_name: str
    post_count: int


class TopPost(BaseModel):
    id: int
    reddit_id: str
    title: str
    score: int
    num_comments: int
    subreddit_name: str
    permalink: str


class TimelineEntry(BaseModel):
    date: str  # YYYY-MM-DD
    post_count: int


class ChartData(BaseModel):
    posts_by_subreddit: list[PostsBySubreddit]
    top_posts: list[TopPost]
    timeline: list[TimelineEntry]


# --- Settings ---

class SettingsRead(BaseModel):
    max_new_posts: int = 10
    top_comments: int = 50
    request_delay: float = 1.0
    max_comment_depth: int = 10


class SettingUpdate(BaseModel):
    max_new_posts: int | None = None
    top_comments: int | None = None
    request_delay: float | None = None
    max_comment_depth: int | None = None


# --- Subreddit Detail Stats ---

class SubredditStats(BaseModel):
    id: int
    name: str
    active: bool
    total_posts: int
    total_comments: int
    last_scraped_at: datetime | None = None
    created_at: datetime
    top_post_title: str | None = None
    top_post_score: int | None = None
    avg_score: float | None = None
    avg_comments: float | None = None
