import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from backend.app.db.session import SessionLocal, get_db
from backend.app.models.models import Comment, Post, Snapshot, Subreddit
from backend.app.schemas.schemas import (
    CommentRead,
    DashboardStats,
    PostRead,
    ScrapeResult,
    SubredditCreate,
    SubredditRead,
)
from backend.app.services.scraper import RedditScraper, ScrapeTask, tasks

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


def _run_scrape_background(task_id: str, subreddit_name: str):
    """Run scrape in a background thread with its own DB session."""
    task = tasks[task_id]
    scraper = RedditScraper()
    db = SessionLocal()
    try:
        def on_progress(current: int, total: int, post_title: str):
            task.progress = current
            task.total = total
            task.current_post = post_title
            task.posts_found = total

        result = scraper.scrape_subreddit(db, subreddit_name, on_progress=on_progress)
        db.commit()
        task.status = "done"
        task.posts_found = result.posts_found
        task.posts_new = result.posts_new
        task.comments_total = result.comments_total
        task.duration_sec = result.duration_sec
    except Exception as e:
        db.rollback()
        task.status = "error"
        task.error = str(e)
    finally:
        scraper.close()
        db.close()


@router.post("/scrape/{subreddit_name}")
async def scrape_subreddit(subreddit_name: str, db: Session = Depends(get_db)):
    """Start an async scrape. Returns a task_id immediately."""
    sub = db.query(Subreddit).filter_by(name=subreddit_name.lower()).first()
    if not sub:
        raise HTTPException(404, f"Subreddit '{subreddit_name}' not tracked. Add it first.")
    if not sub.active:
        raise HTTPException(400, f"Subreddit '{subreddit_name}' is deactivated.")

    task_id = str(uuid.uuid4())[:8]
    task = ScrapeTask(task_id=task_id, subreddit=subreddit_name.lower())
    tasks[task_id] = task

    # Run in background thread (scrape is sync due to time.sleep)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_scrape_background, task_id, subreddit_name.lower())

    return {"task_id": task_id, "subreddit": subreddit_name.lower(), "status": "started"}


@router.get("/scrape/{subreddit_name}/progress")
async def scrape_progress(subreddit_name: str):
    """SSE endpoint for real-time scrape progress."""

    async def event_stream():
        # Find the latest task for this subreddit
        task = None
        for t in reversed(list(tasks.values())):
            if t.subreddit == subreddit_name.lower():
                task = t
                break

        if not task:
            yield f"data: {json.dumps({'error': 'no task found'})}\n\n"
            return

        while True:
            yield f"data: {json.dumps(task.to_dict())}\n\n"
            if task.status in ("done", "error"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a specific scrape task."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task.to_dict()


@router.post("/scrape-all")
async def scrape_all(db: Session = Depends(get_db)):
    subreddits = db.query(Subreddit).filter_by(active=True).all()

    all_task_ids = []
    for sub in subreddits:
        task_id = str(uuid.uuid4())[:8]
        task = ScrapeTask(task_id=task_id, subreddit=sub.name)
        tasks[task_id] = task
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _run_scrape_background, task_id, sub.name)
        all_task_ids.append(task_id)

    return {"tasks": all_task_ids, "total": len(all_task_ids)}


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

    # Get root comments with pagination
    roots = (
        db.query(Comment)
        .filter(
            Comment.post_id == post_id,
            Comment.parent_reddit_id == None  # noqa: E711
        )
        .order_by(Comment.score.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Also handle roots that have parent_reddit_id == post.reddit_id
    alt_roots = (
        db.query(Comment)
        .filter(
            Comment.post_id == post_id,
            Comment.parent_reddit_id == post.reddit_id,
        )
        .order_by(Comment.score.desc())
        .all()
    )

    # Merge and deduplicate
    seen = {c.reddit_id for c in roots}
    for c in alt_roots:
        if c.reddit_id not in seen:
            roots.append(c)
            seen.add(c.reddit_id)

    roots.sort(key=lambda c: c.score, reverse=True)
    roots = roots[:limit]

    # Count total roots for "has more" logic
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

    # Load all non-root comments for this post to build full reply trees
    non_root_ids = [c.reddit_id for c in roots]
    all_replies = (
        db.query(Comment)
        .filter(
            Comment.post_id == post_id,
            Comment.parent_reddit_id.notin_([None, post.reddit_id]),
        )
        .all()
    ) if roots else []

    # Build a temporary parent->children map for all replies
    reply_map: dict[str, list] = {}
    for r in all_replies:
        reply_map.setdefault(r.parent_reddit_id, []).append(r)

    def build_tree(comment):
        """Recursively build comment tree."""
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


# --- Scheduler ---

@router.get("/scheduler/status")
def scheduler_status():
    from backend.app.services.scheduler import scheduler, SCRAPE_INTERVAL_HOURS
    if scheduler is None:
        return {"running": False, "interval_hours": SCRAPE_INTERVAL_HOURS}
    jobs = scheduler.get_jobs()
    next_run = None
    for job in jobs:
        if job.id == "scrape_all_active":
            next_run = str(job.next_run_time) if job.next_run_time else None
            break
    return {
        "running": scheduler.running,
        "interval_hours": SCRAPE_INTERVAL_HOURS,
        "next_run": next_run,
    }


@router.post("/scheduler/trigger")
async def scheduler_trigger():
    """Manually trigger a scrape of all active subreddits."""
    from backend.app.services.scheduler import scrape_all_active
    asyncio.ensure_future(scrape_all_active())
    return {"status": "triggered"}
