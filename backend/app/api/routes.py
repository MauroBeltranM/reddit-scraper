from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from backend.app.db.session import get_db
from backend.app.models.models import Comment, Post, Snapshot, Subreddit
from backend.app.schemas.schemas import (
    CommentRead,
    DashboardStats,
    PostRead,
    ScrapeResult,
    SubredditCreate,
    SubredditRead,
)
from backend.app.services.scraper import RedditScraper

router = APIRouter(prefix="/api", tags=["api"])


# --- Subreddits ---

@router.get("/subreddits", response_model=list[SubredditRead])
def list_subreddits(db: Session = Depends(get_db)):
    return db.query(Subreddit).order_by(Subreddit.name).all()


@router.post("/subreddits", response_model=SubredditRead, status_code=201)
def add_subreddit(body: SubredditCreate, db: Session = Depends(get_db)):
    existing = db.query(Subreddit).filter_by(name=body.name.lower()).first()
    if existing:
        raise HTTPException(409, f"Subreddit '{body.name}' already exists")
    sub = Subreddit(name=body.name.lower())
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


# --- Scraping ---

@router.post("/scrape/{subreddit_name}", response_model=ScrapeResult)
def scrape_subreddit(subreddit_name: str, db: Session = Depends(get_db)):
    sub = db.query(Subreddit).filter_by(name=subreddit_name.lower()).first()
    if not sub:
        raise HTTPException(404, f"Subreddit '{subreddit_name}' not tracked. Add it first.")
    if not sub.active:
        raise HTTPException(400, f"Subreddit '{subreddit_name}' is deactivated.")

    scraper = RedditScraper()
    try:
        result = scraper.scrape_subreddit(db, subreddit_name)
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))
    finally:
        scraper.close()


@router.post("/scrape-all")
def scrape_all(db: Session = Depends(get_db)):
    subreddits = db.query(Subreddit).filter_by(active=True).all()
    scraper = RedditScraper()
    results = []

    for sub in subreddits:
        try:
            result = scraper.scrape_subreddit(db, sub.name)
            results.append(result.model_dump())
        except Exception as e:
            results.append({"error": str(e), "subreddit": sub.name})

    db.commit()
    scraper.close()
    return {"scraped": len(results), "results": results}


# --- Posts ---

@router.get("/posts", response_model=list[PostRead])
def list_posts(
    subreddit_id: int | None = Query(None),
    sort: str = Query("score", pattern="^(score|new|comments)$"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Post).options(joinedload(Post.subreddit))

    if subreddit_id:
        query = query.filter(Post.subreddit_id == subreddit_id)

    if sort == "score":
        query = query.order_by(Post.score.desc())
    elif sort == "new":
        query = query.order_by(Post.scraped_at.desc())
    elif sort == "comments":
        query = query.order_by(Post.num_comments.desc())

    return query.offset(offset).limit(limit).all()


@router.get("/posts/{post_id}", response_model=PostRead)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).options(joinedload(Post.subreddit)).get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@router.get("/posts/{post_id}/comments", response_model=list[CommentRead])
def get_post_comments(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")

    all_comments = (
        db.query(Comment)
        .filter(Comment.post_id == post_id)
        .order_by(Comment.score.desc())
        .all()
    )

    comment_map = {c.reddit_id: c for c in all_comments}
    roots = [c for c in all_comments if c.parent_reddit_id is None or c.parent_reddit_id == post.reddit_id]

    return sorted(
        [CommentRead.from_orm_tree(r) for r in roots],
        key=lambda c: c.score,
        reverse=True,
    )


@router.get("/posts/{post_id}/snapshots")
def get_post_snapshots(post_id: int, db: Session = Depends(get_db)):
    return db.query(Snapshot).filter_by(post_id=post_id).order_by(Snapshot.recorded_at).all()


# --- Comments ---

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


# --- Dashboard ---

@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    return DashboardStats(
        total_subreddits=db.query(Subreddit).count(),
        total_posts=db.query(Post).count(),
        total_comments=db.query(Comment).count(),
        total_snapshots=db.query(Snapshot).count(),
    )
