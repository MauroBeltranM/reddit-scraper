from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from backend.app.db.session import get_db
from backend.app.models.models import Comment, Post, Snapshot, Subreddit
from backend.app.schemas.schemas import CommentRead, PostRead, SnapshotRead

THUMBNAIL_DIR = Path("/app/data/thumbnails")

router = APIRouter(prefix="/api", tags=["posts"])


@router.get("/posts", response_model=list[PostRead])
def list_posts(
    subreddit_id: int | None = Query(None),
    subreddit: str | None = Query(None, description="Filter by subreddit name (case-insensitive)"),
    min_score: int | None = Query(None, description="Minimum post score (inclusive)"),
    max_score: int | None = Query(None, description="Maximum post score (inclusive)"),
    sort_by: str = Query("score", pattern="^(score|date|comments)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    since: str | None = Query(None, pattern="^(24h|7d|30d|all)$"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Post).options(joinedload(Post.subreddit))

    if subreddit_id:
        query = query.filter(Post.subreddit_id == subreddit_id)

    if subreddit:
        sub = db.query(Subreddit).filter(Subreddit.name == subreddit.lower()).first()
        if not sub:
            raise HTTPException(404, f"Subreddit '{subreddit}' not found")
        query = query.filter(Post.subreddit_id == sub.id)

    if min_score is not None:
        query = query.filter(Post.score >= min_score)

    if max_score is not None:
        query = query.filter(Post.score <= max_score)

    since_deltas = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    if since and since != "all":
        cutoff = datetime.utcnow() - since_deltas[since]
        query = query.filter(Post.scraped_at >= cutoff)

    sort_col = (
        Post.score if sort_by == "score"
        else Post.scraped_at if sort_by == "date"
        else Post.num_comments
    )
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    return query.offset(offset).limit(limit).all()


@router.get("/posts/{post_id}", response_model=PostRead)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).options(joinedload(Post.subreddit)).get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@router.get("/posts/{post_id}/comments")
def get_post_comments(
    post_id: int,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")

    roots = (
        db.query(Comment)
        .filter(
            Comment.post_id == post_id,
            Comment.parent_reddit_id == None,  # noqa: E711
        )
        .order_by(Comment.score.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    alt_roots = (
        db.query(Comment)
        .filter(
            Comment.post_id == post_id,
            Comment.parent_reddit_id == post.reddit_id,
        )
        .order_by(Comment.score.desc())
        .all()
    )

    seen = {c.reddit_id for c in roots}
    for c in alt_roots:
        if c.reddit_id not in seen:
            roots.append(c)
            seen.add(c.reddit_id)

    roots.sort(key=lambda c: c.score, reverse=True)
    roots = roots[:limit]

    total_roots = (
        db.query(Comment)
        .filter(
            Comment.post_id == post_id,
            Comment.parent_reddit_id == None,  # noqa: E711
        )
        .count()
    )
    total_alt = (
        db.query(Comment)
        .filter(
            Comment.post_id == post_id,
            Comment.parent_reddit_id == post.reddit_id,
        )
        .count()
    )
    total_roots = max(total_roots, total_alt)

    all_replies = (
        db.query(Comment)
        .filter(
            Comment.post_id == post_id,
            Comment.parent_reddit_id.notin_([None, post.reddit_id]),
        )
        .all()
    ) if roots else []

    reply_map: dict[str, list] = {}
    for r in all_replies:
        reply_map.setdefault(r.parent_reddit_id, []).append(r)

    def build_tree(comment):
        children = reply_map.get(comment.reddit_id, [])
        node = CommentRead.model_validate(comment)
        node.replies = sorted(
            [build_tree(c) for c in children],
            key=lambda c: c.score,
            reverse=True,
        )
        return node

    result = [build_tree(r) for r in roots]

    return {
        "comments": result,
        "total_roots": total_roots,
        "offset": offset,
        "limit": limit,
    }


@router.get("/posts/{post_id}/snapshots", response_model=list[SnapshotRead])
def get_post_snapshots(post_id: int, db: Session = Depends(get_db)):
    return db.query(Snapshot).filter_by(post_id=post_id).order_by(Snapshot.recorded_at).all()


@router.get("/thumbnails/{reddit_id}")
def get_thumbnail(reddit_id: str, db: Session = Depends(get_db)):
    """Serve a locally cached thumbnail image for a post."""
    post = db.query(Post).filter_by(reddit_id=reddit_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    if not post.local_thumbnail:
        raise HTTPException(404, "No thumbnail available for this post")

    thumb_path = THUMBNAIL_DIR / post.local_thumbnail
    if not thumb_path.exists():
        raise HTTPException(404, "Thumbnail file not found on disk")

    return FileResponse(thumb_path, media_type="image/jpeg")


@router.get("/posts/search")
def search_posts(
    q: str = Query(..., min_length=2),
    subreddit_id: int | None = Query(None),
    sort_by: str = Query("score", pattern="^(score|date|comments)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Post).options(joinedload(Post.subreddit)).filter(Post.title.ilike(f"%{q}%"))
    if subreddit_id:
        query = query.filter(Post.subreddit_id == subreddit_id)
    sort_col = (
        Post.score if sort_by == "score"
        else Post.scraped_at if sort_by == "date"
        else Post.num_comments
    )
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    results = query.limit(limit).all()
    return results


@router.get("/comments/search")
def search_comments(
    q: str = Query(..., min_length=2),
    subreddit_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Comment).filter(Comment.body.ilike(f"%{q}%"))
    if subreddit_id:
        post_ids = db.query(Post.id).filter(Post.subreddit_id == subreddit_id).subquery()
        query = query.filter(Comment.post_id.in_(post_ids))
    results = query.order_by(Comment.score.desc()).limit(limit).all()
    return [
        {
            "id": c.id,
            "reddit_id": c.reddit_id,
            "post_id": c.post_id,
            "author": c.author,
            "score": c.score,
            "body": c.body[:300] + ("..." if len(c.body) > 300 else ""),
            "depth": c.depth,
        }
        for c in results
    ]
