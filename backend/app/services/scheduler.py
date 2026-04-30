"""Background scheduler for periodic subreddit scraping."""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.models import Subreddit
from backend.app.services.scraper import RedditScraper

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None

# Default: scrape every 6 hours. Override with SCRAPE_INTERVAL_HOURS env var.
SCRAPE_INTERVAL_HOURS = int(__import__("os").getenv("SCRAPE_INTERVAL_HOURS", "6"))


def _scrape_subreddit_sync(subreddit_name: str):
    """Scrape a single subreddit synchronously (runs in thread executor)."""
    db = SessionLocal()
    try:
        from backend.app.api.routes import get_settings_dict
        cfg = get_settings_dict(db)
        scraper = RedditScraper(
            max_new_posts=cfg["max_new_posts"],
            top_comments=cfg["top_comments"],
            request_delay=cfg["request_delay"],
            max_comment_depth=cfg["max_comment_depth"],
        )
        result = scraper.scrape_subreddit(db, subreddit_name)
        db.commit()
        logger.info(
            "Scheduled scrape of r/%s complete: %d posts found, %d new, %d comments",
            subreddit_name, result.posts_found, result.posts_new, result.comments_total,
        )
        scraper.close()
    except Exception:
        db.rollback()
        logger.exception("Scheduled scrape of r/%s failed", subreddit_name)
    finally:
        db.close()


async def scrape_all_active():
    """Scrape all active subreddits sequentially."""
    db = SessionLocal()
    try:
        active_subs = db.query(Subreddit).filter_by(active=True).all()
        names = [s.name for s in active_subs]
    finally:
        db.close()

    if not names:
        logger.debug("No active subreddits to scrape")
        return

    logger.info("Starting scheduled scrape of %d subreddits: %s", len(names), ", ".join(names))

    import asyncio
    loop = asyncio.get_event_loop()

    for name in names:
        logger.info("Scheduled scrape: r/%s", name)
        await loop.run_in_executor(None, _scrape_subreddit_sync, name)


def start_scheduler():
    """Start the APScheduler instance."""
    global scheduler
    if scheduler is not None:
        return

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        scrape_all_active,
        "interval",
        hours=SCRAPE_INTERVAL_HOURS,
        id="scrape_all_active",
        replace_existing=True,
        next_run_time=datetime.now(),  # Run once on startup
    )
    scheduler.start()
    logger.info("Scheduler started — interval: every %d hours", SCRAPE_INTERVAL_HOURS)


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("Scheduler stopped")
