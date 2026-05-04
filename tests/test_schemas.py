"""Tests for Pydantic schemas."""

from datetime import datetime, timezone

import pytest

from app.schemas.schemas import (
    CommentRead,
    DashboardStats,
    PostRead,
    ScrapeResult,
    SettingsRead,
    SnapshotRead,
    SubredditCreate,
    SubredditRead,
    SubredditStats,
    SubredditUpdate,
)


class TestSubredditSchemas:
    def test_subreddit_create_defaults(self):
        s = SubredditCreate(name="python")
        assert s.name == "python"
        assert s.sort == "hot"
        assert s.timeframe == "all"

    def test_subreddit_create_custom(self):
        s = SubredditCreate(name="programming", sort="new", timeframe="week")
        assert s.sort == "new"
        assert s.timeframe == "week"

    def test_subreddit_update_partial(self):
        u = SubredditUpdate(sort="top")
        assert u.sort == "top"
        assert u.timeframe is None

    def test_subreddit_update_empty(self):
        u = SubredditUpdate()
        assert u.sort is None
        assert u.timeframe is None

    def test_subreddit_read_from_attributes(self):
        """SubredditRead should work with from_attributes=True."""

        class FakeORM:
            id = 1
            name = "python"
            active = True
            sort = "hot"
            timeframe = "all"
            last_scraped_at = None
            total_posts = 42
            created_at = datetime.now(timezone.utc)

        s = SubredditRead.model_validate(FakeORM())
        assert s.name == "python"
        assert s.total_posts == 42
        assert s.last_scraped_at is None


class TestPostSchemas:
    def test_post_read_from_attributes(self):
        class FakeSub:
            id = 1
            name = "python"
            active = True
            sort = "hot"
            timeframe = "all"
            last_scraped_at = None
            total_posts = 0
            created_at = datetime.now(timezone.utc)

        class FakePost:
            id = 10
            reddit_id = "abc123"
            subreddit_id = 1
            title = "Test"
            author = "user1"
            score = 100
            upvote_ratio = 0.9
            num_comments = 5
            url = "https://example.com"
            selftext = None
            post_type = "link"
            permalink = "/r/python/comments/abc123/"
            scraped_at = datetime.now(timezone.utc)
            subreddit = FakeSub()

        p = PostRead.model_validate(FakePost())
        assert p.reddit_id == "abc123"
        assert p.subreddit is not None
        assert p.subreddit.name == "python"

    def test_post_read_without_subreddit(self):
        class FakePost:
            id = 10
            reddit_id = "abc123"
            subreddit_id = 1
            title = "Test"
            author = None
            score = 0
            upvote_ratio = None
            num_comments = 0
            url = None
            selftext = None
            post_type = "link"
            permalink = "/r/test/"
            scraped_at = datetime.now(timezone.utc)
            subreddit = None

        p = PostRead.model_validate(FakePost())
        assert p.subreddit is None


class TestCommentSchemas:
    def test_comment_read(self):
        now = datetime.now(timezone.utc)
        c = CommentRead(
            id=1,
            reddit_id="c01",
            post_id=10,
            parent_reddit_id=None,
            author="user1",
            score=5,
            body="Hello",
            depth=0,
            scraped_at=now,
        )
        assert c.body == "Hello"
        assert c.replies == []

    def test_comment_read_with_replies(self):
        now = datetime.now(timezone.utc)
        reply = CommentRead(
            id=2,
            reddit_id="c02",
            post_id=10,
            parent_reddit_id="c01",
            author="user2",
            score=3,
            body="Reply",
            depth=1,
            scraped_at=now,
        )
        parent = CommentRead(
            id=1,
            reddit_id="c01",
            post_id=10,
            parent_reddit_id=None,
            author="user1",
            score=5,
            body="Hello",
            depth=0,
            scraped_at=now,
            replies=[reply],
        )
        assert len(parent.replies) == 1
        assert parent.replies[0].reddit_id == "c02"


class TestSnapshotSchemas:
    def test_snapshot_read(self):
        now = datetime.now(timezone.utc)
        s = SnapshotRead(id=1, post_id=10, score=100, num_comments=25, recorded_at=now)
        assert s.score == 100
        assert s.num_comments == 25


class TestScrapeResult:
    def test_scrape_result(self):
        r = ScrapeResult(
            subreddit="python",
            posts_found=25,
            posts_new=3,
            comments_total=150,
            duration_sec=12.5,
        )
        assert r.subreddit == "python"
        assert r.posts_new == 3


class TestDashboardStats:
    def test_dashboard_stats(self):
        s = DashboardStats(total_subreddits=5, total_posts=100, total_comments=500, total_snapshots=200)
        assert s.total_posts == 100


class TestSettingsRead:
    def test_settings_defaults(self):
        s = SettingsRead()
        assert s.max_new_posts == 10
        assert s.top_comments == 50
        assert s.request_delay == 1.0
        assert s.max_comment_depth == 10

    def test_settings_custom(self):
        s = SettingsRead(max_new_posts=20, request_delay=2.0)
        assert s.max_new_posts == 20
        assert s.request_delay == 2.0


class TestSubredditStats:
    def test_subreddit_stats(self):
        now = datetime.now(timezone.utc)
        s = SubredditStats(
            id=1,
            name="python",
            active=True,
            total_posts=50,
            total_comments=200,
            last_scraped_at=now,
            created_at=now,
            top_post_title="Best post",
            top_post_score=999,
            avg_score=45.5,
            avg_comments=12.3,
        )
        assert s.name == "python"
        assert s.avg_score == 45.5
