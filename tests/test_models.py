"""Tests for SQLAlchemy models: Subreddit, Post, Comment, Snapshot, Setting."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.models import Base, Comment, Post, Setting, Snapshot, Subreddit


@pytest.fixture
def engine():
    """In-memory SQLite engine with tables created."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine):
    """Fresh DB session per test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# --- Subreddit ---


class TestSubreddit:
    def test_create_subreddit(self, db):
        sub = Subreddit(name="python")
        db.add(sub)
        db.commit()

        result = db.query(Subreddit).filter_by(name="python").first()
        assert result is not None
        assert result.name == "python"
        assert result.active is True
        assert result.sort == "hot"
        assert result.timeframe == "all"
        assert result.total_posts == 0
        assert isinstance(result.created_at, datetime)

    def test_subreddit_unique_name(self, db):
        sub1 = Subreddit(name="python")
        sub2 = Subreddit(name="python")
        db.add(sub1)
        db.commit()
        db.add(sub2)
        with pytest.raises(Exception):
            db.commit()

    def test_subreddit_with_custom_sort(self, db):
        sub = Subreddit(name="programming", sort="new", timeframe="week")
        db.add(sub)
        db.commit()

        result = db.query(Subreddit).filter_by(name="programming").first()
        assert result.sort == "new"
        assert result.timeframe == "week"

    def test_subreddit_last_scraped_at_none_initially(self, db):
        sub = Subreddit(name="datascience")
        db.add(sub)
        db.commit()

        assert sub.last_scraped_at is None


# --- Post ---


class TestPost:
    def _make_subreddit(self, db, name="python"):
        sub = Subreddit(name=name)
        db.add(sub)
        db.flush()
        return sub

    def test_create_post(self, db):
        sub = self._make_subreddit(db)
        post = Post(
            subreddit_id=sub.id,
            reddit_id="abc123",
            title="Test post",
            permalink="/r/python/comments/abc123/",
        )
        db.add(post)
        db.commit()

        result = db.query(Post).first()
        assert result.title == "Test post"
        assert result.reddit_id == "abc123"
        assert result.post_type == "link"
        assert result.score == 0
        assert result.num_comments == 0

    def test_post_relationship_to_subreddit(self, db):
        sub = self._make_subreddit(db)
        post = Post(
            subreddit_id=sub.id,
            reddit_id="xyz789",
            title="Linked post",
            permalink="/r/python/comments/xyz789/",
        )
        db.add(post)
        db.commit()

        result = db.query(Post).first()
        assert result.subreddit is not None
        assert result.subreddit.name == "python"

    def test_post_all_fields(self, db):
        sub = self._make_subreddit(db)
        post = Post(
            subreddit_id=sub.id,
            reddit_id="full001",
            title="Full post",
            author="testuser",
            score=42,
            upvote_ratio=0.95,
            num_comments=7,
            url="https://example.com",
            selftext="Body text",
            post_type="self",
            permalink="/r/python/comments/full001/",
        )
        db.add(post)
        db.commit()

        result = db.query(Post).first()
        assert result.author == "testuser"
        assert result.score == 42
        assert result.upvote_ratio == 0.95
        assert result.num_comments == 7
        assert result.url == "https://example.com"
        assert result.selftext == "Body text"
        assert result.post_type == "self"

    def test_post_reddit_id_unique(self, db):
        sub = self._make_subreddit(db)
        p1 = Post(subreddit_id=sub.id, reddit_id="dup01", title="A", permalink="/a")
        p2 = Post(subreddit_id=sub.id, reddit_id="dup01", title="B", permalink="/b")
        db.add(p1)
        db.commit()
        db.add(p2)
        with pytest.raises(Exception):
            db.commit()

    def test_post_optional_fields_nullable(self, db):
        sub = self._make_subreddit(db)
        post = Post(
            subreddit_id=sub.id,
            reddit_id="opt001",
            title="Minimal",
            permalink="/r/python/comments/opt001/",
            author=None,
            url=None,
            selftext=None,
        )
        db.add(post)
        db.commit()

        result = db.query(Post).first()
        assert result.author is None
        assert result.url is None
        assert result.selftext is None

    def test_post_thumbnail_fields(self, db):
        sub = self._make_subreddit(db)
        post = Post(
            subreddit_id=sub.id,
            reddit_id="thumb01",
            title="Image post",
            post_type="image",
            permalink="/r/python/comments/thumb01/",
            thumbnail_url="https://preview.redd.it/thumb01.jpg",
            local_thumbnail="thumb01.jpg",
        )
        db.add(post)
        db.commit()

        result = db.query(Post).first()
        assert result.thumbnail_url == "https://preview.redd.it/thumb01.jpg"
        assert result.local_thumbnail == "thumb01.jpg"
        assert result.post_type == "image"

    def test_post_thumbnail_fields_nullable(self, db):
        sub = self._make_subreddit(db)
        post = Post(
            subreddit_id=sub.id,
            reddit_id="nothumb",
            title="Link post",
            permalink="/r/python/comments/nothumb/",
        )
        db.add(post)
        db.commit()

        result = db.query(Post).first()
        assert result.thumbnail_url is None
        assert result.local_thumbnail is None


# --- Comment ---


class TestComment:
    def _make_post(self, db):
        sub = Subreddit(name="test")
        db.add(sub)
        db.flush()
        post = Post(
            subreddit_id=sub.id,
            reddit_id="c_post01",
            title="Post for comments",
            permalink="/r/test/comments/c_post01/",
        )
        db.add(post)
        db.flush()
        return post

    def test_create_comment(self, db):
        post = self._make_post(db)
        comment = Comment(
            post_id=post.id,
            reddit_id="comm001",
            body="Hello world",
            score=5,
            depth=0,
        )
        db.add(comment)
        db.commit()

        result = db.query(Comment).first()
        assert result.body == "Hello world"
        assert result.reddit_id == "comm001"
        assert result.score == 5
        assert result.depth == 0

    def test_comment_post_relationship(self, db):
        post = self._make_post(db)
        comment = Comment(
            post_id=post.id,
            reddit_id="comm002",
            body="Nice post",
        )
        db.add(comment)
        db.commit()

        result = db.query(Comment).first()
        assert result.post is not None
        assert result.post.reddit_id == "c_post01"

    def test_comment_with_parent(self, db):
        post = self._make_post(db)
        comment = Comment(
            post_id=post.id,
            reddit_id="comm003",
            parent_reddit_id="t1_comm002",
            body="Reply",
            depth=1,
        )
        db.add(comment)
        db.commit()

        result = db.query(Comment).first()
        assert result.parent_reddit_id == "t1_comm002"
        assert result.depth == 1

    def test_comment_defaults(self, db):
        post = self._make_post(db)
        comment = Comment(
            post_id=post.id,
            reddit_id="comm004",
            body="Default values",
        )
        db.add(comment)
        db.commit()

        result = db.query(Comment).first()
        assert result.score == 0
        assert result.depth == 0


# --- Snapshot ---


class TestSnapshot:
    def _make_post(self, db):
        sub = Subreddit(name="snap_test")
        db.add(sub)
        db.flush()
        post = Post(
            subreddit_id=sub.id,
            reddit_id="snap_post01",
            title="Snapshot post",
            permalink="/r/test/comments/snap_post01/",
        )
        db.add(post)
        db.flush()
        return post

    def test_create_snapshot(self, db):
        post = self._make_post(db)
        snap = Snapshot(post_id=post.id, score=100, num_comments=25)
        db.add(snap)
        db.commit()

        result = db.query(Snapshot).first()
        assert result.score == 100
        assert result.num_comments == 25
        assert result.post_id == post.id
        assert isinstance(result.recorded_at, datetime)

    def test_snapshot_post_relationship(self, db):
        post = self._make_post(db)
        snap = Snapshot(post_id=post.id, score=50, num_comments=10)
        db.add(snap)
        db.commit()

        result = db.query(Snapshot).first()
        assert result.post is not None
        assert result.post.reddit_id == "snap_post01"

    def test_multiple_snapshots_for_same_post(self, db):
        post = self._make_post(db)
        for i in range(3):
            db.add(Snapshot(post_id=post.id, score=10 * i, num_comments=i))
        db.commit()

        snapshots = db.query(Snapshot).filter_by(post_id=post.id).all()
        assert len(snapshots) == 3
        scores = sorted([s.score for s in snapshots])
        assert scores == [0, 10, 20]


# --- Setting ---


class TestSetting:
    def test_create_setting(self, db):
        s = Setting(key="max_new_posts", value="10")
        db.add(s)
        db.commit()

        result = db.query(Setting).get("max_new_posts")
        assert result is not None
        assert result.value == "10"

    def test_setting_primary_key_is_key(self, db):
        s = Setting(key="request_delay", value="1.5")
        db.add(s)
        db.commit()

        result = db.query(Setting).get("request_delay")
        assert result.key == "request_delay"
