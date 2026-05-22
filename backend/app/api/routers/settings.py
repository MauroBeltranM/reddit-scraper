import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.models import Setting
from backend.app.schemas.schemas import SettingUpdate, SettingsRead

router = APIRouter(prefix="/api", tags=["settings"])

SETTINGS_DEFAULTS = {
    "max_new_posts": str(os.getenv("MAX_NEW_POSTS", "10")),
    "top_comments": str(os.getenv("TOP_COMMENTS", "50")),
    "request_delay": str(os.getenv("REQUEST_DELAY", "1.0")),
    "max_comment_depth": str(os.getenv("MAX_COMMENT_DEPTH", "10")),
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


@router.get("/settings/oauth-status")
def get_oauth_status():
    """Return Reddit OAuth connection status."""
    from backend.app.config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, settings as app_settings
    from backend.app.services.reddit_auth import get_reddit_token

    configured = app_settings.reddit_oauth_enabled
    has_id = bool(REDDIT_CLIENT_ID)
    has_secret = bool(REDDIT_CLIENT_SECRET)

    active = False
    if configured:
        token = get_reddit_token()
        active = token is not None

    return {
        "enabled": configured,
        "connected": active,
        "has_client_id": has_id,
        "has_client_secret": has_secret,
    }


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
