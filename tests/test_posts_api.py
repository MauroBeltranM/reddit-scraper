"""Tests for GET /api/posts endpoint filters: subreddit, min_score, max_score."""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root is importable for 'backend.' prefixed imports
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
    """TestClient with DB dependency override using just the posts router."""
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
def seed_data(db_session):
    """Insert subreddits and posts for filtering tests."""
    sub_python = Subreddit(name="python", active=True)
    sub_js = Subreddit(name="javascript", active=True)
    db_session.add_all([sub_python, sub_js])
    db_session.flush()

    posts = [
        Post(subreddit_id=sub_python.id, reddit_id="p1", title="Python post high score",
             score=500, num_comments=10, permalink="/r/python/p1"),
        Post(subreddit_id=sub_python.id, reddit_id="p2", title="Python post low score",
             score=5, num_comments=1, permalink="/r/python/p2"),
        Post(subreddit_id=sub_python.id, reddit_id="p3", title="Python mid score",
             score=100, num_comments=50, permalink="/r/python/p3"),
        Post(subreddit_id=sub_js.id, reddit_id="p4", title="JS post high",
             score=300, num_comments=20, permalink="/r/javascript/p4"),
        Post(subreddit_id=sub_js.id, reddit_id="p5", title="JS post low",
             score=2, num_comments=0, permalink="/r/javascript/p5"),
    ]
    db_session.add_all(posts)
    db_session.commit()
    return {"sub_python": sub_python, "sub_js": sub_js}


class TestSubredditFilter:
    def test_filter_by_subreddit_name(self, client, seed_data):
        resp = client.get("/api/posts", params={"subreddit": "python"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert all(p["subreddit"]["name"] == "python" for p in data)

    def test_filter_by_subreddit_case_insensitive(self, client, seed_data):
        resp = client.get("/api/posts", params={"subreddit": "JavaScript"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_filter_by_subreddit_not_found(self, client, seed_data):
        resp = client.get("/api/posts", params={"subreddit": "nonexistent"})
        assert resp.status_code == 404

    def test_no_subreddit_filter_returns_all(self, client, seed_data):
        resp = client.get("/api/posts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5


class TestMinScoreFilter:
    def test_min_score_filters_low_posts(self, client, seed_data):
        resp = client.get("/api/posts", params={"min_score": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3  # scores: 500, 100, 300
        assert all(p["score"] >= 100 for p in data)

    def test_min_score_500(self, client, seed_data):
        resp = client.get("/api/posts", params={"min_score": 500})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["score"] == 500

    def test_min_score_higher_than_all(self, client, seed_data):
        resp = client.get("/api/posts", params={"min_score": 9999})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0


class TestMaxScoreFilter:
    def test_max_score_filters_high_posts(self, client, seed_data):
        resp = client.get("/api/posts", params={"max_score": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3  # scores: 5, 100, 2
        assert all(p["score"] <= 100 for p in data)

    def test_max_score_2(self, client, seed_data):
        resp = client.get("/api/posts", params={"max_score": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["score"] == 2

    def test_max_score_lower_than_all(self, client, seed_data):
        resp = client.get("/api/posts", params={"max_score": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0


class TestScoreRangeFilter:
    def test_min_and_max_score_range(self, client, seed_data):
        resp = client.get("/api/posts", params={"min_score": 5, "max_score": 100})
        assert resp.status_code == 200
        data = resp.json()
        scores = {p["score"] for p in data}
        assert scores == {5, 100}

    def test_narrow_range(self, client, seed_data):
        resp = client.get("/api/posts", params={"min_score": 200, "max_score": 400})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["score"] == 300

    def test_range_with_no_results(self, client, seed_data):
        resp = client.get("/api/posts", params={"min_score": 600, "max_score": 700})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0


class TestCombinedFilters:
    def test_subreddit_and_score_range(self, client, seed_data):
        resp = client.get("/api/posts", params={
            "subreddit": "python", "min_score": 50, "max_score": 200,
        })
        assert resp.status_code == 200
        data = resp.json()
        scores = {p["score"] for p in data}
        assert scores == {100}

    def test_subreddit_and_min_score(self, client, seed_data):
        resp = client.get("/api/posts", params={
            "subreddit": "javascript", "min_score": 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["score"] == 300

    def test_subreddit_with_sort_new(self, client, seed_data):
        resp = client.get("/api/posts", params={
            "subreddit": "python", "sort": "new",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
