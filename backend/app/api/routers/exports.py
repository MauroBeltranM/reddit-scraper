import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from backend.app.db.session import get_db
from backend.app.models.models import Comment, Post, Subreddit

router = APIRouter(prefix="/api", tags=["exports"])

POST_CSV_FIELDS = [
    "id", "reddit_id", "subreddit", "title", "author", "score",
    "upvote_ratio", "num_comments", "url", "post_type", "permalink", "scraped_at",
]
COMMENT_CSV_FIELDS = [
    "id", "reddit_id", "post_id", "post_title", "author", "score",
    "body", "depth", "scraped_at",
]


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

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COMMENT_CSV_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        io.StringIO(buf.getvalue()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename_prefix}.csv"'},
    )
