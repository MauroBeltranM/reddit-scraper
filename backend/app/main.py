import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.api.routes import router
from backend.app.db.session import engine
from backend.app.models.models import Base

STATIC_DIR = Path("/app/static")


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
    def startup():
        Base.metadata.create_all(bind=engine)

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
