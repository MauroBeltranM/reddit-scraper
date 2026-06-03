"""Tests for DELETE /api/posts/{id} endpoint with cascade."""

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

from backend.app.models.models import Base, Comment, Post, Snapshot, Subreddit
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
def seeded_post(db_session):
    """Create a subreddit, post with comments and snapshots."""
    sub = Subreddit(name="test", active=True)
    db_session.add(sub)
    db_session.flush()

    post = Post(
        subreddit_id=sub.id,
        reddit_id="del1",
        title="Post to delete",
        score=42,
        num_comments=2,
        permalink="/r/test/del1",
    )
    db_session.add(post)
    db_session.flush()

    c1 = Comment(
        post_id=post.id,
        reddit_id="c1",
        body="First comment",
        score=10,
        depth=0,
    )
    c2 = Comment(
        post_id=post.id,
        reddit_id="c2",
        body="Second comment",
        score=5,
        depth=1,
        parent_reddit_id="c1",
    )
    snap = Snapshot(post_id=post.id, score=42, num_comments=2)
    db_session.add_all([c1, c2, snap])
    db_session.commit()

    return {"post": post, "subreddit": sub, "comments": [c1, c2], "snapshot": snap}


class TestDeletePost:
    def test_delete_existing_post(self, client, db_session, seeded_post):
        post_id = seeded_post["post"].id
        resp = client.delete(f"/api/posts/{post_id}")
        assert resp.status_code == 204

        # Verify post is gone
        assert db_session.query(Post).get(post_id) is None

    def test_delete_cascades_comments(self, client, db_session, seeded_post):
        post_id = seeded_post["post"].id
        client.delete(f"/api/posts/{post_id}")
        assert db_session.query(Comment).filter(Comment.post_id == post_id).count() == 0

    def test_delete_cascades_snapshots(self, client, db_session, seeded_post):
        post_id = seeded_post["post"].id
        client.delete(f"/api/posts/{post_id}")
        assert db_session.query(Snapshot).filter(Snapshot.post_id == post_id).count() == 0

    def test_delete_nonexistent_post_404(self, client, db_session):
        resp = client.delete("/api/posts/99999")
        assert resp.status_code == 404

    def test_delete_does_not_affect_other_posts(self, client, db_session, seeded_post):
        # Create another post in the same subreddit
        other = Post(
            subreddit_id=seeded_post["subreddit"].id,
            reddit_id="other1",
            title="Other post",
            score=1,
            num_comments=0,
            permalink="/r/test/other1",
        )
        db_session.add(other)
        db_session.commit()
        other_id = other.id

        client.delete(f"/api/posts/{seeded_post['post'].id}")

        # Other post still exists
        assert db_session.query(Post).get(other_id) is not None

    def test_delete_twice_second_is_404(self, client, db_session, seeded_post):
        post_id = seeded_post["post"].id
        resp1 = client.delete(f"/api/posts/{post_id}")
        assert resp1.status_code == 204

        resp2 = client.delete(f"/api/posts/{post_id}")
        assert resp2.status_code == 404

    def test_delete_removes_thumbnail_file(self, client, db_session, seeded_post, tmp_path, monkeypatch):
        from backend.app.api.routers import posts as posts_module

        monkeypatch.setattr(posts_module, "THUMBNAIL_DIR", tmp_path)

        post = seeded_post["post"]
        thumb_file = tmp_path / "test_thumb.jpg"
        thumb_file.write_bytes(b"fake image data")
        post.local_thumbnail = "test_thumb.jpg"
        db_session.commit()

        assert thumb_file.exists()
        resp = client.delete(f"/api/posts/{post.id}")
        assert resp.status_code == 204
        assert not thumb_file.exists()

    def test_delete_without_thumbnail_no_error(self, client, db_session, seeded_post):
        post = seeded_post["post"]
        post.local_thumbnail = None
        db_session.commit()

        resp = client.delete(f"/api/posts/{post.id}")
        assert resp.status_code == 204
