import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.api.routes import router
from backend.app.db.session import engine
from backend.app.models.models import Base
from backend.app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path("/app/static")


def _migrate_db(engine):
    """Add missing columns to existing tables (lightweight SQLite migrations)."""
    import sqlalchemy
    with engine.connect() as conn:
        # Check if 'sort' column exists in subreddits
        if engine.dialect.name == "sqlite":
            result = conn.execute(sqlalchemy.text("PRAGMA table_info(subreddits)"))
            columns = {row[1] for row in result}
            if "sort" not in columns:
                conn.execute(sqlalchemy.text("ALTER TABLE subreddits ADD COLUMN sort VARCHAR(20) DEFAULT 'hot'"))
                conn.commit()
                logger.info("Migration: added 'sort' column to subreddits")
            if "timeframe" not in columns:
                conn.execute(sqlalchemy.text("ALTER TABLE subreddits ADD COLUMN timeframe VARCHAR(20) DEFAULT 'all'"))
                conn.commit()
                logger.info("Migration: added 'timeframe' column to subreddits")
        else:
            # PostgreSQL: check information_schema
            result = conn.execute(sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='subreddits'"
            ))
            columns = {row[0] for row in result}
            if "sort" not in columns:
                conn.execute(sqlalchemy.text("ALTER TABLE subreddits ADD COLUMN sort VARCHAR(20) DEFAULT 'hot'"))
                conn.commit()
                logger.info("Migration: added 'sort' column to subreddits")
            if "timeframe" not in columns:
                conn.execute(sqlalchemy.text("ALTER TABLE subreddits ADD COLUMN timeframe VARCHAR(20) DEFAULT 'all'"))
                conn.commit()
                logger.info("Migration: added 'timeframe' column to subreddits")


# Auto-scheduler can be disabled via env var
AUTO_SCRAPE = os.getenv("AUTO_SCRAPE", "true").lower() in ("true", "1", "yes")


def create_app() -> FastAPI:
    app = FastAPI(title="Reddit Scraper", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup():
        # Lightweight migration: add new columns if they don't exist
        _migrate_db(engine)
        Base.metadata.create_all(bind=engine)
        if AUTO_SCRAPE:
            start_scheduler()
            logger.info("Auto-scraper enabled")

    @app.on_event("shutdown")
    async def shutdown():
        stop_scheduler()

    # API routes first (registered before static fallback)
    app.include_router(router)

    # Static assets (exact files)
    if STATIC_DIR.exists():
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # SPA fallback: serve index.html for any non-API, non-static path
        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            # Skip API routes (they should already be handled above)
            if full_path.startswith("api/"):
                return {"detail": "Not found"}
            file = STATIC_DIR / full_path
            if file.is_file():
                return FileResponse(file)
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
