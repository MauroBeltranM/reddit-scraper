from backend.app.api.routers.subreddits import router as subreddits_router
from backend.app.api.routers.scrapes import router as scrapes_router
from backend.app.api.routers.posts import router as posts_router
from backend.app.api.routers.dashboard import router as dashboard_router
from backend.app.api.routers.settings import router as settings_router
from backend.app.api.routers.exports import router as exports_router

__all__ = [
    "subreddits_router",
    "scrapes_router",
    "posts_router",
    "dashboard_router",
    "settings_router",
    "exports_router",
]
