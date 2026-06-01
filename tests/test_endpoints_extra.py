"""Integration tests for scrape, export, and dashboard endpoints.

Covers:
- POST /api/scrape/{subreddit_name} (mocked scraper)
- GET /api/export/posts
- GET /api/dashboard/stats
- GET /api/dashboard/chart-data
- PATCH /api/subreddits/{id}
- GET /api/subreddits/{id}/stats
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

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
from backend.app.api.routers.scrapes import router as scrapes_router
from backend.app.api.routers.exports import router as exports_router
from backend.app.api.routers.dashboard import router as dashboard_router


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
    app.include_router(scrapes_router)
    app.include_router(exports_router)
    app.include_router(dashboard_router)

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
    db_session.add_all([sub_python, sub_js])
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
            subreddit_id=sub_js.id, reddit_id="p3",
            title="JS post medium", score=300, num_comments=20,
            permalink="/r/javascript/p3", author="charlie",
            scraped_at=now - timedelta(days=3),
        ),
    ]
    db_session.add_all(posts)
    db_session.flush()

    # Snapshots for p1
    snapshots = [
        Snapshot(post_id=posts[0].id, score=400, num_comments=8,
                 recorded_at=now - timedelta(hours=4)),
        Snapshot(post_id=posts[0].id, score=500, num_comments=10,
                 recorded_at=now),
    ]
    db_session.add_all(snapshots)

    # Comments for p1
    comments = [
        Comment(post_id=posts[0].id, reddit_id="c1", author="diana",
                score=50, body="Great post!", depth=0, parent_reddit_id=None),
        Comment(post_id=posts[0].id, reddit_id="c2", author="eve",
                score=30, body="I agree", depth=1, parent_reddit_id="c1"),
    ]
    db_session.add_all(comments)

    db_session.commit()
    return {
        "sub_python": sub_python,
        "sub_js": sub_js,
        "posts": posts,
    }


# ===========================================================================
# 1. GET /api/dashboard/stats
# ===========================================================================

class TestDashboardStats:
    def test_stats_with_data(self, client, seed_data):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_subreddits"] == 2
        assert data["total_posts"] == 3
        assert data["total_comments"] == 2
        assert data["total_snapshots"] == 2

    def test_stats_empty_db(self, client, db_session):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_subreddits"] == 0
        assert data["total_posts"] == 0
        assert data["total_comments"] == 0
        assert data["total_snapshots"] == 0

    def test_stats_fields_present(self, client, seed_data):
        resp = client.get("/api/stats")
        data = resp.json()
        for key in ("total_subreddits", "total_posts", "total_comments", "total_snapshots"):
            assert key in data


# ===========================================================================
# 2. GET /api/dashboard/chart-data
# ===========================================================================

class TestDashboardChartData:
    def test_chart_data_structure(self, client, seed_data):
        resp = client.get("/api/dashboard/chart-data")
        assert resp.status_code == 200
        data = resp.json()
        assert "posts_by_subreddit" in data
        assert "top_posts" in data
        assert "timeline" in data

    def test_posts_by_subreddit(self, client, seed_data):
        resp = client.get("/api/dashboard/chart-data")
        data = resp.json()
        by_sub = data["posts_by_subreddit"]
        # We have 2 subreddits
        assert len(by_sub) == 2
        names = {s["subreddit_name"] for s in by_sub}
        assert names == {"python", "javascript"}
        # Check counts
        counts = {s["subreddit_name"]: s["post_count"] for s in by_sub}
        assert counts["python"] == 2
        assert counts["javascript"] == 1

    def test_top_posts(self, client, seed_data):
        resp = client.get("/api/dashboard/chart-data")
        data = resp.json()
        top = data["top_posts"]
        assert len(top) <= 10
        # First should be highest score
        assert top[0]["score"] == 500
        assert top[0]["subreddit_name"] == "python"

    def test_chart_data_empty_db(self, client, db_session):
        resp = client.get("/api/dashboard/chart-data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["posts_by_subreddit"] == []
        assert data["top_posts"] == []
        assert data["timeline"] == []


# ===========================================================================
# 3. GET /api/export/posts
# ===========================================================================

class TestExportPosts:
    def test_export_csv_all(self, client, seed_data):
        resp = client.get("/api/export/posts", params={"format": "csv"})
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "posts_all" in resp.headers["content-disposition"]
        lines = resp.text.strip().split("\n")
        assert len(lines) == 4  # header + 3 posts
        assert "title" in lines[0]

    def test_export_json_all(self, client, seed_data):
        resp = client.get("/api/export/posts", params={"format": "json"})
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        data = resp.json()
        assert len(data) == 3

    def test_export_csv_by_subreddit(self, client, seed_data):
        resp = client.get("/api/export/posts", params={
            "subreddit": "python", "format": "csv",
        })
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        assert len(lines) == 3  # header + 2 python posts
        assert "posts_python" in resp.headers["content-disposition"]

    def test_export_json_by_subreddit(self, client, seed_data):
        resp = client.get("/api/export/posts", params={
            "subreddit": "javascript", "format": "json",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["subreddit"] == "javascript"

    def test_export_nonexistent_subreddit(self, client, seed_data):
        resp = client.get("/api/export/posts", params={"subreddit": "nonexistent"})
        assert resp.status_code == 404

    def test_export_empty_db(self, client, db_session):
        resp = client.get("/api/export/posts", params={"format": "csv"})
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        assert len(lines) == 1  # just header


# ===========================================================================
# 4. POST /api/scrape/{subreddit_name} (mocked)
# ===========================================================================

class TestScrapeEndpoint:
    @patch("backend.app.api.routers.scrapes._run_scrape_background")
    def test_scrape_starts_task(self, mock_run, client, seed_data):
        resp = client.post("/api/scrape/python")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["subreddit"] == "python"
        assert "task_id" in data

    @patch("backend.app.api.routers.scrapes._run_scrape_background")
    def test_scrape_unknown_subreddit(self, mock_run, client, seed_data):
        resp = client.post("/api/scrape/nonexistent")
        assert resp.status_code == 404

    @patch("backend.app.api.routers.scrapes._run_scrape_background")
    def test_scrape_task_id_is_unique(self, mock_run, client, seed_data):
        resp1 = client.post("/api/scrape/python")
        resp2 = client.post("/api/scrape/python")
        assert resp1.json()["task_id"] != resp2.json()["task_id"]

    @patch("backend.app.api.routers.scrapes._run_scrape_background")
    def test_scrape_progress_endpoint(self, mock_run, client, seed_data):
        # Start a scrape (mocked so it won't actually run)
        resp = client.post("/api/scrape/python")
        task_id = resp.json()["task_id"]

        # Check task status
        resp2 = client.get(f"/api/tasks/{task_id}")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["task_id"] == task_id
        assert data["subreddit"] == "python"

    @patch("backend.app.api.routers.scrapes._run_scrape_background")
    def test_task_not_found(self, mock_run, client, seed_data):
        resp = client.get("/api/tasks/nonexistent123")
        assert resp.status_code == 404


# ===========================================================================
# 5. PATCH /api/subreddits/{id} + GET /api/subreddits/{id}/stats
# ===========================================================================

class TestSubredditDetail:
    def test_patch_subreddit_sort(self, client, seed_data):
        sub_id = seed_data["sub_python"].id
        resp = client.patch(f"/api/subreddits/{sub_id}", json={"sort": "new"})
        assert resp.status_code == 200
        assert resp.json()["sort"] == "new"

    def test_patch_subreddit_invalid_sort(self, client, seed_data):
        sub_id = seed_data["sub_python"].id
        resp = client.patch(f"/api/subreddits/{sub_id}", json={"sort": "invalid"})
        assert resp.status_code == 400

    def test_patch_subreddit_timeframe(self, client, seed_data):
        sub_id = seed_data["sub_python"].id
        resp = client.patch(f"/api/subreddits/{sub_id}", json={"timeframe": "week"})
        assert resp.status_code == 200
        assert resp.json()["timeframe"] == "week"

    def test_subreddit_stats(self, client, seed_data):
        sub_id = seed_data["sub_python"].id
        resp = client.get(f"/api/subreddits/{sub_id}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "python"
        assert data["total_posts"] == 2
        assert data["total_comments"] == 2
        assert data["top_post_title"] == "Python post high score"
        assert data["top_post_score"] == 500
        assert data["avg_score"] is not None

    def test_subreddit_stats_not_found(self, client, seed_data):
        resp = client.get("/api/subreddits/99999/stats")
        assert resp.status_code == 404

    def test_subreddit_stats_empty_subreddit(self, client, db_session):
        sub = Subreddit(name="empty", active=True)
        db_session.add(sub)
        db_session.commit()
        resp = client.get(f"/api/subreddits/{sub.id}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_posts"] == 0
        assert data["total_comments"] == 0
        assert data["top_post_title"] is None
        assert data["avg_score"] is None


# ===========================================================================
# 6. GET /api/posts/{id} edge cases
# ===========================================================================

class TestPostDetailEdgeCases:
    def test_post_includes_all_fields(self, client, seed_data):
        """Verify all expected fields are present in a post response."""
        post_id = seed_data["posts"][0].id
        resp = client.get(f"/api/posts/{post_id}")
        assert resp.status_code == 200
        data = resp.json()
        expected_fields = [
            "id", "reddit_id", "subreddit_id", "title", "author",
            "score", "num_comments", "permalink", "post_type", "scraped_at",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    def test_post_not_found_returns_404(self, client, seed_data):
        resp = client.get("/api/posts/99999")
        assert resp.status_code == 404

    def test_get_comments_tree_structure(self, client, seed_data):
        """Verify comment tree has proper nesting."""
        post_id = seed_data["posts"][0].id
        resp = client.get(f"/api/posts/{post_id}/comments")
        assert resp.status_code == 200
        data = resp.json()
        # c1 is root, c2 is child of c1
        roots = data["comments"]
        assert len(roots) >= 1
        root = roots[0]
        assert "replies" in root
        assert "body" in root
        assert "score" in root
