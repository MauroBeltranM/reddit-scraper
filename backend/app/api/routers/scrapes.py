import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal, get_db
from backend.app.models.models import Subreddit
from backend.app.api.routers.settings import get_settings_dict
from backend.app.services.scraper import RedditScraper, ScrapeTask, tasks

router = APIRouter(prefix="/api", tags=["scrapes"])


def _run_scrape_background(task_id: str, subreddit_name: str, sort: str = "hot", timeframe: str = "all"):
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

        result = scraper.scrape_subreddit(db, subreddit_name, sort=sort, timeframe=timeframe, on_progress=on_progress, task=task)
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

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_scrape_background, task_id, subreddit_name.lower(), sub.sort, sub.timeframe)

    return {"task_id": task_id, "subreddit": subreddit_name.lower(), "status": "started"}


@router.get("/scrape/{subreddit_name}/progress")
async def scrape_progress(subreddit_name: str):
    """SSE endpoint for real-time scrape progress."""

    async def event_stream():
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
        loop.run_in_executor(None, _run_scrape_background, task_id, sub.name, sub.sort, sub.timeframe)
        all_task_ids.append(task_id)

    return {"tasks": all_task_ids, "total": len(all_task_ids)}
