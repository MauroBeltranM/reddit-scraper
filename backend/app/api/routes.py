import asyncio
import csv
import io
import json
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.app.db.session import SessionLocal, get_db
from backend.app.models.models import Comment, Post, Setting, Snapshot, Subreddit
from backend.app.schemas.schemas import (
    ChartData,
    CommentRead,
    DashboardStats,
    PostsBySubreddit,
    PostRead,
    ScrapeResult,
    SettingUpdate,
    SettingsRead,
    SubredditCreate,
    SubredditRead,
    SubredditStats,
    TimelineEntry,
    TopPost,
)
from backend.app.services.scraper import RedditScraper, ScrapeTask, tasks

router = APIRouter(prefix="/api", tags=["api"])


# --- Settings helpers ---

SETTINGS_DEFAULTS = {
    "max_new_posts": str(__import__("os").getenv("MAX_NEW_POSTS", "10")),
    "top_comments": str(__import__("os").getenv("TOP_COMMENTS", "50")),
    "request_delay": str(__import__("os").getenv("REQUEST_DELAY", "1.0")),
    "max_comment_depth": str(__import__("os").getenv("MAX_COMMENT_DEPTH", "10")),
}

SETTINGS_TYPES = {
    "max_new_posts": int,
    "top_comments": int,
    "request_delay": float,
    "max_comment_depth": int,
}


def get_settings_dict(db: Session) -> dict:
    """Load all settings from DB, falling back to env/defaults."""
    rows = db.query(Setting).all()
    db_map = {r.key: r.value for r in rows}
    result = {}
    for key, default in SETTINGS_DEFAULTS.items():
        val = db_map.get(key, default)
        result[key] = SETTINGS_TYPES[key](val)
    return result


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


# --- Scraping ---


def _run_scrape_background(task_id: str, subreddit_name: str):
    """Run scrape in a background thread with its own DB session."""
    task = tasks[task_id]
    db = SessionLocal()
    try:
        cfg = get_settings_dict(db)
        scraper = RedditScraper(
            max_new_posts=cfg["max_new_posts"],
            top_comments=cfg["top_comments"],
            request_delay=cfg["request_delay"],
            max_comment_depth=cfg["max_comment_depth"],
        )
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

@router.get("/posts/search")
def search_posts(
    q: str = Query(..., min_length=2),
    subreddit_id: int | None = Query(None),
    sort: str = Query("score", pattern="^(score|new|comments)$"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Post).options(joinedload(Post.subreddit)).filter(Post.title.ilike(f"%{q}%"))
    if subreddit_id:
        query = query.filter(Post.subreddit_id == subreddit_id)
    if sort == "score":
        query = query.order_by(Post.score.desc())
    elif sort == "new":
        query = query.order_by(Post.scraped_at.desc())
    elif sort == "comments":
        query = query.order_by(Post.num_comments.desc())
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


# --- Dashboard ---

@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    return DashboardStats(
        total_subreddits=db.query(Subreddit).count(),
        total_posts=db.query(Post).count(),
        total_comments=db.query(Comment).count(),
        total_snapshots=db.query(Snapshot).count(),
    )


@router.get("/dashboard/chart-data", response_model=ChartData)
def dashboard_chart_data(db: Session = Depends(get_db)):
    """Return aggregated data for dashboard charts."""
    # 1) Posts per subreddit
    posts_by_sub = (
        db.query(
            Subreddit.id.label("subreddit_id"),
            Subreddit.name.label("subreddit_name"),
            func.count(Post.id).label("post_count"),
        )
        .join(Post, Subreddit.id == Post.subreddit_id, isouter=True)
        .group_by(Subreddit.id, Subreddit.name)
        .order_by(func.count(Post.id).desc())
        .all()
    )
    posts_by_subreddit = [
        PostsBySubreddit(
            subreddit_id=r.subreddit_id,
            subreddit_name=r.subreddit_name,
            post_count=r.post_count,
        )
        for r in posts_by_sub
    ]

    # 2) Top 10 posts by score
    top_rows = (
        db.query(Post, Subreddit.name.label("subreddit_name"))
        .join(Subreddit, Post.subreddit_id == Subreddit.id)
        .order_by(Post.score.desc())
        .limit(10)
        .all()
    )
    top_posts = [
        TopPost(
            id=p.Post.id,
            reddit_id=p.Post.reddit_id,
            title=p.Post.title,
            score=p.Post.score,
            num_comments=p.Post.num_comments,
            subreddit_name=p.subreddit_name,
            permalink=p.Post.permalink,
        )
        for p in top_rows
    ]

    # 3) Timeline: posts grouped by day (last 30 days)
    since = datetime.utcnow() - timedelta(days=30)
    timeline_rows = (
        db.query(
            func.date(Post.scraped_at).label("date"),
            func.count(Post.id).label("post_count"),
        )
        .filter(Post.scraped_at >= since)
        .group_by(func.date(Post.scraped_at))
        .order_by(func.date(Post.scraped_at))
        .all()
    )
    timeline = [
        TimelineEntry(
            date=str(r.date) if r.date else "",
            post_count=r.post_count,
        )
        for r in timeline_rows
    ]

    return ChartData(
        posts_by_subreddit=posts_by_subreddit,
        top_posts=top_posts,
        timeline=timeline,
    )


# --- Settings ---

@router.get("/settings", response_model=SettingsRead)
def get_settings(db: Session = Depends(get_db)):
    return get_settings_dict(db)


@router.put("/settings", response_model=SettingsRead)
def update_settings(body: SettingUpdate, db: Session = Depends(get_db)):
    for key, value in body.model_dump().items():
        if value is None:
            continue
        if key not in SETTINGS_DEFAULTS:
            continue
        row = db.query(Setting).filter_by(key=key).first()
        if row:
            row.value = str(value)
        else:
            db.add(Setting(key=key, value=str(value)))
    db.commit()
    return get_settings_dict(db)


# --- Export ---

POST_CSV_FIELDS = ["id", "reddit_id", "subreddit", "title", "author", "score", "upvote_ratio", "num_comments", "url", "post_type", "permalink", "scraped_at"]
COMMENT_CSV_FIELDS = ["id", "reddit_id", "post_id", "post_title", "author", "score", "body", "depth", "scraped_at"]


@router.get("/export/posts")
def export_posts(
    subreddit: str | None = Query(None),
    format: str = Query("csv", pattern="^(csv|json)$"),
    db: Session = Depends(get_db),
):
    """Export all posts for a subreddit (or all) as CSV or JSON."""
    query = db.query(Post).options(joinedload(Post.subreddit))
    if subreddit:
        sub = db.query(Subreddit).filter_by(name=subreddit.lower()).first()
        if not sub:
            raise HTTPException(404, f"Subreddit '{subreddit}' not found")
        query = query.filter(Post.subreddit_id == sub.id)

    posts = query.order_by(Post.score.desc()).all()

    rows = []
    for p in posts:
        rows.append({
            "id": p.id,
            "reddit_id": p.reddit_id,
            "subreddit": p.subreddit.name if p.subreddit else "",
            "title": p.title,
            "author": p.author or "",
            "score": p.score,
            "upvote_ratio": p.upvote_ratio or "",
            "num_comments": p.num_comments,
            "url": p.url or "",
            "post_type": p.post_type,
            "permalink": p.permalink,
            "scraped_at": str(p.scraped_at),
        })

    filename_prefix = f"posts_{subreddit}" if subreddit else "posts_all"

    if format == "json":
        content = json.dumps(rows, ensure_ascii=False, indent=2)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename_prefix}.json"'},
        )

    # CSV
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=POST_CSV_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        io.StringIO(buf.getvalue()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename_prefix}.csv"'},
    )


@router.get("/export/comments")
def export_comments(
    post_id: int = Query(...),
    format: str = Query("csv", pattern="^(csv|json)$"),
    db: Session = Depends(get_db),
):
    """Export all comments for a post as CSV or JSON."""
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")

    comments = db.query(Comment).filter(Comment.post_id == post_id).order_by(Comment.score.desc()).all()

    rows = []
    for c in comments:
        rows.append({
            "id": c.id,
            "reddit_id": c.reddit_id,
            "post_id": c.post_id,
            "post_title": post.title,
            "author": c.author or "",
            "score": c.score,
            "body": c.body,
            "depth": c.depth,
            "scraped_at": str(c.scraped_at),
        })

    filename_prefix = f"comments_post{post_id}"

    if format == "json":
        content = json.dumps(rows, ensure_ascii=False, indent=2)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename_prefix}.json"'},
        )

    # CSV
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COMMENT_CSV_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        io.StringIO(buf.getvalue()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename_prefix}.csv"'},
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
