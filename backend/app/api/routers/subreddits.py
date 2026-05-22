from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.models import Comment, Post, Subreddit
from backend.app.schemas.schemas import (
    SubredditCreate,
    SubredditRead,
    SubredditStats,
    SubredditUpdate,
)

router = APIRouter(prefix="/api", tags=["subreddits"])


@router.get("/subreddits", response_model=list[SubredditRead])
def list_subreddits(db: Session = Depends(get_db)):
    return db.query(Subreddit).order_by(Subreddit.name).all()


@router.post("/subreddits", response_model=SubredditRead, status_code=201)
def add_subreddit(body: SubredditCreate, db: Session = Depends(get_db)):
    existing = db.query(Subreddit).filter_by(name=body.name.lower()).first()
    if existing:
        raise HTTPException(409, f"Subreddit '{body.name}' already exists")
    sub = Subreddit(
        name=body.name.lower(),
        sort=body.sort,
        timeframe=body.timeframe,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/subreddits/{subreddit_id}", status_code=204)
def remove_subreddit(subreddit_id: int, db: Session = Depends(get_db)):
    sub = db.query(Subreddit).get(subreddit_id)
    if not sub:
        raise HTTPException(404, "Subreddit not found")
    db.delete(sub)
    db.commit()


@router.patch("/subreddits/{subreddit_id}", response_model=SubredditRead)
def update_subreddit(subreddit_id: int, body: SubredditUpdate, db: Session = Depends(get_db)):
    sub = db.query(Subreddit).get(subreddit_id)
    if not sub:
        raise HTTPException(404, "Subreddit not found")
    if body.sort is not None:
        if body.sort not in ("hot", "new", "top"):
            raise HTTPException(400, "sort must be one of: hot, new, top")
        sub.sort = body.sort
    if body.timeframe is not None:
        if body.timeframe not in ("hour", "day", "week", "month", "year", "all"):
            raise HTTPException(400, "timeframe must be one of: hour, day, week, month, year, all")
        sub.timeframe = body.timeframe
    db.commit()
    db.refresh(sub)
    return sub


@router.get("/subreddits/{subreddit_id}/stats", response_model=SubredditStats)
def subreddit_stats(subreddit_id: int, db: Session = Depends(get_db)):
    sub = db.query(Subreddit).get(subreddit_id)
    if not sub:
        raise HTTPException(404, "Subreddit not found")

    post_agg = db.query(
        func.count(Post.id).label("total_posts"),
        func.avg(Post.score).label("avg_score"),
        func.avg(Post.num_comments).label("avg_comments"),
    ).filter(Post.subreddit_id == subreddit_id).first()

    total_comments = (
        db.query(func.count(Comment.id))
        .join(Post, Comment.post_id == Post.id)
        .filter(Post.subreddit_id == subreddit_id)
        .scalar()
    )

    top_post = (
        db.query(Post)
        .filter(Post.subreddit_id == subreddit_id)
        .order_by(Post.score.desc())
        .first()
    )

    return SubredditStats(
        id=sub.id,
        name=sub.name,
        active=sub.active,
        total_posts=post_agg.total_posts or 0,
        total_comments=total_comments or 0,
        last_scraped_at=sub.last_scraped_at,
        created_at=sub.created_at,
        top_post_title=top_post.title if top_post else None,
        top_post_score=top_post.score if top_post else None,
        avg_score=round(post_agg.avg_score, 1) if post_agg.avg_score else None,
        avg_comments=round(post_agg.avg_comments, 1) if post_agg.avg_comments else None,
    )
