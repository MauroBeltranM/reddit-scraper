"""Integration tests for main API routes using TestClient + in-memory SQLite.

Tests cover: GET /api/posts, GET /api/subreddits, POST /api/subreddits,
GET /api/posts/{id}/snapshots, DELETE /api/posts/{id}, and edge cases.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.models.models import Base, Comment, Post, Snapshot, Subreddit
from backend.app.db.session import get_db
from backend.app.api.routers.posts import router as posts_router
from backend.app.api.routers.subreddits import router as subreddits_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(posts_router)
    app.include_router(subreddits_router)

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


@pytest.fixture
def seed_data(db_session):
    """Seed database with subreddits, posts, snapshots, and comments."""
    sub_python = Subreddit(name="python", active=True, sort="hot", timeframe="all")
    sub_js = Subreddit(name="javascript", active=True, sort="new", timeframe="week")
    sub_rust = Subreddit(name="rust", active=True, sort="top", timeframe="month")
    db_session.add_all([sub_python, sub_js, sub_rust])
    db_session.flush()

    now = datetime.now(timezone.utc)

    posts = [
        Post(
            subreddit_id=sub_python.id, reddit_id="p1",
            title="Python post high score", score=500, num_comments=10,
            permalink="/r/python/p1", author="alice",
            scraped_at=now - timedelta(hours=2),
        ),
        Post(
            subreddit_id=sub_python.id, reddit_id="p2",
            title="Python post low score", score=5, num_comments=1,
            permalink="/r/python/p2", author="bob",
            scraped_at=now - timedelta(hours=1),
        ),
        Post(
            subreddit_id=sub_python.id, reddit_id="p3",
            title="Python mid score", score=100, num_comments=50,
            permalink="/r/python/p3",
            scraped_at=now - timedelta(days=10),
        ),
        Post(
            subreddit_id=sub_js.id, reddit_id="p4",
            title="JS post high", score=300, num_comments=20,
            permalink="/r/javascript/p4",
            scraped_at=now - timedelta(days=3),
        ),
        Post(
            subreddit_id=sub_js.id, reddit_id="p5",
            title="JS post low", score=2, num_comments=0,
            permalink="/r/javascript/p5",
            scraped_at=now - timedelta(days=40),
        ),
        Post(
            subreddit_id=sub_rust.id, reddit_id="p6",
            title="Rust awesome", score=800, num_comments=100,
            permalink="/r/rust/p6", post_type="link", url="https://rust-lang.org",
            scraped_at=now,
        ),
    ]
    db_session.add_all(posts)
    db_session.flush()

    # Snapshots for p1
    snapshots = [
        Snapshot(post_id=posts[0].id, score=400, num_comments=8,
                 recorded_at=now - timedelta(hours=4)),
        Snapshot(post_id=posts[0].id, score=450, num_comments=9,
                 recorded_at=now - timedelta(hours=2)),
        Snapshot(post_id=posts[0].id, score=500, num_comments=10,
                 recorded_at=now),
    ]
    db_session.add_all(snapshots)

    # Comments for p1
    comments = [
        Comment(post_id=posts[0].id, reddit_id="c1", author="charlie",
                score=50, body="Great post!", depth=0, parent_reddit_id=None),
        Comment(post_id=posts[0].id, reddit_id="c2", author="diana",
                score=30, body="I agree", depth=1, parent_reddit_id="c1"),
        Comment(post_id=posts[0].id, reddit_id="c3", author="eve",
                score=10, body="Nice", depth=0, parent_reddit_id=None),
    ]
    db_session.add_all(comments)

    db_session.commit()
    return {
        "sub_python": sub_python,
        "sub_js": sub_js,
        "sub_rust": sub_rust,
        "posts": posts,
    }


# ---------------------------------------------------------------------------
# 1. GET /api/posts — filters & sorting
# ---------------------------------------------------------------------------

class TestListPosts:
    """Test GET /api/posts with various filters and sort options."""

    def test_get_all_posts_default(self, client, seed_data):
        resp = client.get("/api/posts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6
        # Default sort by score desc
        assert data[0]["score"] == 800

    def test_sort_by_date_desc(self, client, seed_data):
        resp = client.get("/api/posts", params={"sort_by": "date", "order": "desc"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6
        # Most recent first (rust post is now)
        assert data[0]["reddit_id"] == "p6"

    def test_sort_by_date_asc(self, client, seed_data):
        resp = client.get("/api/posts", params={"sort_by": "date", "order": "asc"})
        assert resp.status_code == 200
        data = resp.json()
        # Oldest first (js post low is 40 days ago)
        assert data[0]["reddit_id"] == "p5"

    def test_sort_by_comments(self, client, seed_data):
        resp = client.get("/api/posts", params={"sort_by": "comments", "order": "desc"})
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["num_comments"] == 100  # rust post

    def test_filter_by_subreddit_id(self, client, seed_data):
        sub_id = seed_data["sub_python"].id
        resp = client.get("/api/posts", params={"subreddit_id": sub_id})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert all(p["subreddit_id"] == sub_id for p in data)

    def test_filter_by_subreddit_name(self, client, seed_data):
        resp = client.get("/api/posts", params={"subreddit": "rust"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Rust awesome"

    def test_filter_by_min_score(self, client, seed_data):
        resp = client.get("/api/posts", params={"min_score": 300})
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["score"] >= 300 for p in data)
        scores = {p["score"] for p in data}
        assert scores == {500, 300, 800}

    def test_filter_since_24h(self, client, seed_data):
        resp = client.get("/api/posts", params={"since": "24h"})
        assert resp.status_code == 200
        data = resp.json()
        # Only posts scraped in last 24h: p6 (now), p2 (1h ago), p1 (2h ago)
        ids = {p["reddit_id"] for p in data}
        assert "p6" in ids
        assert "p1" in ids
        assert "p2" in ids
        assert "p3" not in ids  # 10 days ago

    def test_filter_since_7d(self, client, seed_data):
        resp = client.get("/api/posts", params={"since": "7d"})
        assert resp.status_code == 200
        data = resp.json()
        ids = {p["reddit_id"] for p in data}
        assert "p4" in ids  # 3 days ago
        assert "p5" not in ids  # 40 days ago

    def test_filter_since_all(self, client, seed_data):
        resp = client.get("/api/posts", params={"since": "all"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6

    def test_pagination_limit_offset(self, client, seed_data):
        resp = client.get("/api/posts", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        resp2 = client.get("/api/posts", params={"limit": 2, "offset": 2})
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2) == 2

        # No overlap
        ids1 = {p["id"] for p in data}
        ids2 = {p["id"] for p in data2}
        assert ids1.isdisjoint(ids2)

    def test_empty_results(self, client, seed_data):
        resp = client.get("/api/posts", params={"min_score": 99999})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_combined_subreddit_and_min_score_and_sort(self, client, seed_data):
        resp = client.get("/api/posts", params={
            "subreddit": "python", "min_score": 10, "sort_by": "score", "order": "asc",
        })
        assert resp.status_code == 200
        data = resp.json()
        scores = [p["score"] for p in data]
        assert scores == sorted(scores)  # ascending
        assert all(p["score"] >= 10 for p in data)
        assert all(p["subreddit"]["name"] == "python" for p in data)


# ---------------------------------------------------------------------------
# 2. GET /api/subreddits
# ---------------------------------------------------------------------------

class TestListSubreddits:
    def test_get_all_subreddits(self, client, seed_data):
        resp = client.get("/api/subreddits")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        names = {s["name"] for s in data}
        assert names == {"python", "javascript", "rust"}

    def test_subreddits_sorted_by_name(self, client, seed_data):
        resp = client.get("/api/subreddits")
        data = resp.json()
        names = [s["name"] for s in data]
        assert names == sorted(names)

    def test_subreddit_fields(self, client, seed_data):
        resp = client.get("/api/subreddits")
        sub = resp.json()[0]
        assert "id" in sub
        assert "name" in sub
        assert "active" in sub
        assert "sort" in sub
        assert "timeframe" in sub
        assert "created_at" in sub


# ---------------------------------------------------------------------------
# 3. POST /api/subreddits
# ---------------------------------------------------------------------------

class TestAddSubreddit:
    def test_add_new_subreddit(self, client, db_session):
        resp = client.post("/api/subreddits", json={
            "name": "golang", "sort": "hot", "timeframe": "all",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "golang"
        assert data["active"] is True
        assert data["sort"] == "hot"
        assert "id" in data

    def test_add_duplicate_subreddit_returns_409(self, client, seed_data):
        resp = client.post("/api/subreddits", json={
            "name": "python", "sort": "hot", "timeframe": "all",
        })
        assert resp.status_code == 409

    def test_add_subreddit_lowercases_name(self, client, db_session):
        resp = client.post("/api/subreddits", json={
            "name": "ReactJS", "sort": "new", "timeframe": "day",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "reactjs"


# ---------------------------------------------------------------------------
# 4. GET /api/posts/{id}/snapshots
# ---------------------------------------------------------------------------

class TestGetSnapshots:
    def test_get_snapshots_for_post(self, client, seed_data):
        post_id = seed_data["posts"][0].id
        resp = client.get(f"/api/posts/{post_id}/snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # Should be ordered by recorded_at
        scores = [s["score"] for s in data]
        assert scores == [400, 450, 500]

    def test_get_snapshots_empty(self, client, seed_data):
        # rust post has no snapshots
        post_id = seed_data["posts"][5].id
        resp = client.get(f"/api/posts/{post_id}/snapshots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_snapshots_post_not_found(self, client, seed_data):
        resp = client.get("/api/posts/99999/snapshots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_snapshot_fields(self, client, seed_data):
        post_id = seed_data["posts"][0].id
        resp = client.get(f"/api/posts/{post_id}/snapshots")
        snap = resp.json()[0]
        assert "id" in snap
        assert "post_id" in snap
        assert "score" in snap
        assert "num_comments" in snap
        assert "recorded_at" in snap


# ---------------------------------------------------------------------------
# 5. DELETE /api/posts/{id}
# ---------------------------------------------------------------------------

class TestDeletePost:
    def test_delete_existing_post(self, client, db_session, seed_data):
        post_id = seed_data["posts"][0].id
        resp = client.delete(f"/api/posts/{post_id}")
        assert resp.status_code == 204

        # Verify post is gone
        resp2 = client.get(f"/api/posts/{post_id}")
        assert resp2.status_code == 404

    def test_delete_post_removes_comments(self, client, db_session, seed_data):
        post_id = seed_data["posts"][0].id
        client.delete(f"/api/posts/{post_id}")

        # Comments should be gone too
        remaining = db_session.query(Comment).filter(Comment.post_id == post_id).all()
        assert len(remaining) == 0

    def test_delete_post_removes_snapshots(self, client, db_session, seed_data):
        post_id = seed_data["posts"][0].id
        client.delete(f"/api/posts/{post_id}")

        remaining = db_session.query(Snapshot).filter(Snapshot.post_id == post_id).all()
        assert len(remaining) == 0

    def test_delete_nonexistent_post_returns_404(self, client, seed_data):
        resp = client.delete("/api/posts/99999")
        assert resp.status_code == 404

    def test_delete_preserves_other_posts(self, client, db_session, seed_data):
        post_id = seed_data["posts"][0].id
        client.delete(f"/api/posts/{post_id}")

        resp = client.get("/api/posts")
        data = resp.json()
        assert len(data) == 5
        assert all(p["id"] != post_id for p in data)


# ---------------------------------------------------------------------------
# 6. GET /api/posts/{id} — single post
# ---------------------------------------------------------------------------

class TestGetSinglePost:
    def test_get_existing_post(self, client, seed_data):
        post_id = seed_data["posts"][0].id
        resp = client.get(f"/api/posts/{post_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == post_id
        assert data["title"] == "Python post high score"
        assert data["author"] == "alice"
        assert data["subreddit"]["name"] == "python"

    def test_get_post_not_found(self, client, seed_data):
        resp = client.get("/api/posts/99999")
        assert resp.status_code == 404

    def test_post_includes_subreddit_relation(self, client, seed_data):
        post_id = seed_data["posts"][5].id  # rust
        resp = client.get(f"/api/posts/{post_id}")
        data = resp.json()
        assert data["subreddit"]["name"] == "rust"
        assert data["url"] == "https://rust-lang.org"


# ---------------------------------------------------------------------------
# 7. GET /api/posts/{id}/comments
# ---------------------------------------------------------------------------

class TestGetPostComments:
    def test_get_comments_for_post(self, client, seed_data):
        post_id = seed_data["posts"][0].id
        resp = client.get(f"/api/posts/{post_id}/comments")
        assert resp.status_code == 200
        data = resp.json()
        assert "comments" in data
        assert "total_roots" in data
        assert data["total_roots"] >= 2  # c1 and c3 are root-level

    def test_get_comments_post_not_found(self, client, seed_data):
        resp = client.get("/api/posts/99999/comments")
        assert resp.status_code == 404

    def test_comments_empty_for_post_without_comments(self, client, seed_data):
        post_id = seed_data["posts"][5].id  # rust post has no comments
        resp = client.get(f"/api/posts/{post_id}/comments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["comments"] == []
        assert data["total_roots"] == 0
