"""Integration tests for full-text search on GET /api/posts/search.

Covers:
- LIKE fallback (SQLite) with title and body matching
- Short query (<3 chars) always uses LIKE
- language query param is accepted
- subreddit_id filter works with search
- sort_by and order work with search
"""

import sys
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

from backend.app.models.models import Base, Post, Subreddit
from backend.app.db.session import get_db
from backend.app.api.routers.posts import router


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
    app.include_router(router)

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


@pytest.fixture
def search_data(db_session):
    """Insert subreddits and posts for search tests."""
    sub = Subreddit(name="python", active=True)
    sub2 = Subreddit(name="worldnews", active=True)
    db_session.add_all([sub, sub2])
    db_session.flush()

    posts = [
        Post(
            subreddit_id=sub.id, reddit_id="s1",
            title="FastAPI web framework tutorial",
            selftext="Learn how to build APIs with Python",
            score=200, num_comments=15, permalink="/r/python/s1",
        ),
        Post(
            subreddit_id=sub.id, reddit_id="s2",
            title="Async programming in Python",
            selftext="Understanding asyncio and coroutines",
            score=150, num_comments=8, permalink="/r/python/s2",
        ),
        Post(
            subreddit_id=sub.id, reddit_id="s3",
            title="Python data science libraries",
            selftext="NumPy, Pandas, and Matplotlib overview",
            score=300, num_comments=25, permalink="/r/python/s3",
        ),
        Post(
            subreddit_id=sub2.id, reddit_id="s4",
            title="Climate summit 2025 results",
            selftext="World leaders agree on new targets",
            score=500, num_comments=100, permalink="/r/worldnews/s4",
        ),
        Post(
            subreddit_id=sub2.id, reddit_id="s5",
            title="Elections in Europe latest updates",
            selftext="New coalition government formed",
            score=400, num_comments=50, permalink="/r/worldnews/s5",
        ),
    ]
    db_session.add_all(posts)
    db_session.commit()
    return {"sub_python": sub, "sub_worldnews": sub2}


class TestSearchLikeFallback:
    """Tests using SQLite (LIKE fallback since no tsvector)."""

    def test_search_by_title(self, client, search_data):
        resp = client.get("/api/posts/search", params={"q": "Python"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3  # posts with "Python" in title or body

    def test_search_by_body(self, client, search_data):
        resp = client.get("/api/posts/search", params={"q": "asyncio"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any("async" in p["title"].lower() for p in data)

    def test_search_no_results(self, client, search_data):
        resp = client.get("/api/posts/search", params={"q": "xyznonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0

    def test_search_short_query_uses_like(self, client, search_data):
        """Short queries (<3 chars) should still work with LIKE fallback."""
        resp = client.get("/api/posts/search", params={"q": "Py"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_search_minimum_length(self, client, search_data):
        """Queries with <2 chars should be rejected."""
        resp = client.get("/api/posts/search", params={"q": "P"})
        assert resp.status_code == 422


class TestSearchFilters:
    def test_search_with_subreddit_filter(self, client, search_data):
        sub = search_data["sub_python"]
        resp = client.get("/api/posts/search", params={"q": "Python", "subreddit_id": sub.id})
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["subreddit_id"] == sub.id for p in data)

    def test_search_with_sort_date(self, client, search_data):
        resp = client.get("/api/posts/search", params={"q": "Python", "sort_by": "date"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_search_with_sort_asc(self, client, search_data):
        resp = client.get("/api/posts/search", params={"q": "Python", "sort_by": "score", "order": "asc"})
        assert resp.status_code == 200
        data = resp.json()
        if len(data) >= 2:
            assert data[0]["score"] <= data[-1]["score"]


class TestSearchLanguageParam:
    def test_language_spanish_accepted(self, client, search_data):
        resp = client.get("/api/posts/search", params={"q": "Python", "language": "spanish"})
        assert resp.status_code == 200

    def test_language_english_accepted(self, client, search_data):
        resp = client.get("/api/posts/search", params={"q": "Python", "language": "english"})
        assert resp.status_code == 200

    def test_language_invalid_rejected(self, client, search_data):
        resp = client.get("/api/posts/search", params={"q": "Python", "language": "french"})
        assert resp.status_code == 422


class TestSearchBodyField:
    """Verify search also matches body/selftext, not just title."""

    def test_match_in_selftext_not_title(self, client, search_data):
        """'NumPy' appears only in selftext of post s3."""
        resp = client.get("/api/posts/search", params={"q": "NumPy"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any("data science" in p["title"].lower() for p in data)

    def test_match_in_both_title_and_body(self, client, search_data):
        """'Python' appears in both title and body of multiple posts."""
        resp = client.get("/api/posts/search", params={"q": "Python"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
