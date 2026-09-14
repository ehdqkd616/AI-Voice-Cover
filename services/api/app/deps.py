"""§14.1 usage quota + request identity helpers."""

import hashlib
from datetime import date

from fastapi import Cookie, Depends, Request

from common.config import get_settings
from common.db.models import User
from common.db.session import SessionLocal
from common.redis_client import get_redis

from .errors import ApiError
from .session_store import SESSION_COOKIE_NAME, get_session_user_id


def get_current_user(session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)) -> User | None:
    if not session_id:
        return None
    user_id = get_session_user_id(session_id)
    if not user_id:
        return None
    db = SessionLocal()
    try:
        return db.get(User, user_id)
    finally:
        db.close()


def require_user(current_user: User | None = Depends(get_current_user)) -> User:
    if current_user is None:
        raise ApiError("NOT_AUTHENTICATED", "로그인이 필요합니다.")
    return current_user


def require_admin(current_user: User = Depends(require_user)) -> User:
    if not current_user.is_admin:
        raise ApiError("FORBIDDEN", "관리자만 접근할 수 있습니다.")
    return current_user


def client_subject(request: Request, current_user: User | None = None) -> str:
    """user:{uuid} when logged in, else ip:{hash} — anonymous fallback (§14.1)."""
    if current_user is not None:
        return f"user:{current_user.id}"
    ip = request.client.host if request.client else "unknown"
    digest = hashlib.sha256(ip.encode()).hexdigest()[:16]
    return f"ip:{digest}"


def check_quota(subject: str, action: str, limit: int) -> None:
    key = f"quota:{subject}:{action}:{date.today().isoformat()}"
    r = get_redis()
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 86400)
    count, _ = pipe.execute()
    if count > limit:
        raise ApiError(
            "RATE_LIMITED",
            f"{action} 일일 한도({limit}회)를 초과했습니다.",
            {"action": action, "limit": limit},
        )


def enforce_download_quota(request: Request, current_user: User | None = Depends(get_current_user)) -> None:
    settings = get_settings()
    check_quota(client_subject(request, current_user), "download", settings.anon_daily_download_limit)


def enforce_separate_quota(request: Request, current_user: User | None = Depends(get_current_user)) -> None:
    settings = get_settings()
    check_quota(client_subject(request, current_user), "separate", settings.anon_daily_separate_limit)
