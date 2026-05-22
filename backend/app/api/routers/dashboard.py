import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.app.db.session import get_db
from backend.app.models.models import Comment, Post, Snapshot, Subreddit
from backend.app.schemas.schemas import (
    ChartData,
    DashboardStats,
    PostsBySubreddit,
    TimelineEntry,
    TopPost,
)

router = APIRouter(prefix="/api", tags=["dashboard"])


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
