import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router
from app.db.session import engine
from app.models.models import Base

STATIC_DIR = Path(__file__).parent.parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Reddit Scraper",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create tables on startup
    @app.on_event("startup")
    def startup():
        Base.metadata.create_all(bind=engine)

    # API routes
    app.include_router(router)

    # Serve Vue SPA static files in production
    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            """Serve index.html for any non-API route (SPA routing)."""
            file = STATIC_DIR / full_path
            if file.is_file():
                return FileResponse(file)
            return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
