"""Server-side session store — Redis-backed, cookie carries only an opaque token."""

import secrets

from common.redis_client import get_redis

SESSION_COOKIE_NAME = "session_id"
SESSION_TTL_SEC = 60 * 60 * 24 * 30  # 30 days
_SESSION_KEY_PREFIX = "session:"


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    get_redis().set(f"{_SESSION_KEY_PREFIX}{token}", user_id, ex=SESSION_TTL_SEC)
    return token


def get_session_user_id(token: str) -> str | None:
    """Sliding expiration: GETEX resets the TTL on every authenticated read."""
    return get_redis().getex(f"{_SESSION_KEY_PREFIX}{token}", ex=SESSION_TTL_SEC)


def delete_session(token: str) -> None:
    get_redis().delete(f"{_SESSION_KEY_PREFIX}{token}")
