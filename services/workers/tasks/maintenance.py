"""Canary healthcheck + circuit breaker, TTL cleanup."""

from datetime import datetime, timezone

from common.db.models import Media
from common.db.session import session_scope
from common.redis_client import get_redis
from common.storage import delete_object
from common.ytdlp import fetch_info

from ..celery_app import app

# A short, stable Creative Commons video used purely to detect yt-dlp/bot-detection breakage.
CANARY_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
CANARY_FAIL_THRESHOLD = 3
CANARY_STREAK_KEY = "canary:fail_streak"
CIRCUIT_KEY = "circuit:download_disabled"


@app.task(name="tasks.canary_healthcheck")
def canary_healthcheck() -> dict:
    r = get_redis()
    try:
        fetch_info(CANARY_URL)
        r.set("canary:last_ok", datetime.now(timezone.utc).isoformat())
        r.delete(CANARY_STREAK_KEY)
        r.delete(CIRCUIT_KEY)
        return {"ok": True}
    except Exception as exc:
        streak = r.incr(CANARY_STREAK_KEY)
        r.expire(CANARY_STREAK_KEY, 3600)
        if streak >= CANARY_FAIL_THRESHOLD:
            # Circuit breaker: downloads go dark, separate/convert/dsp stay up.
            r.set(CIRCUIT_KEY, "1", ex=1800)
        return {"ok": False, "error": str(exc), "streak": streak}


@app.task(name="tasks.purge_expired_media")
def purge_expired_media() -> dict:
    now = datetime.now(timezone.utc)
    deleted = 0
    with session_scope() as db:
        expired = db.query(Media).filter(Media.expires_at < now).all()
        for media in expired:
            delete_object(media.storage_key)
            db.delete(media)
            deleted += 1
    return {"deleted": deleted}
