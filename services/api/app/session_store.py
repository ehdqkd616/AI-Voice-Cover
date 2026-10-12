"""Server-side session store — Redis-backed, cookie carries only an opaque token.

회원별 세션 목록(user_sessions:{id})도 함께 관리해, 정지·임시 비밀번호 발급 때 그 회원의 세션을 모두 끊는다.
"""

import secrets

from common.redis_client import get_redis

SESSION_COOKIE_NAME = "session_id"
SESSION_TTL_SEC = 60 * 60 * 24 * 30  # 30 days
_SESSION_KEY_PREFIX = "session:"
_USER_SESSIONS_PREFIX = "user_sessions:"


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    r = get_redis()
    r.set(f"{_SESSION_KEY_PREFIX}{token}", user_id, ex=SESSION_TTL_SEC)
    r.sadd(f"{_USER_SESSIONS_PREFIX}{user_id}", token)
    r.expire(f"{_USER_SESSIONS_PREFIX}{user_id}", SESSION_TTL_SEC)
    return token


def get_session_user_id(token: str) -> str | None:
    """Sliding expiration: GETEX resets the TTL on every authenticated read."""
    return get_redis().getex(f"{_SESSION_KEY_PREFIX}{token}", ex=SESSION_TTL_SEC)


def delete_session(token: str) -> None:
    get_redis().delete(f"{_SESSION_KEY_PREFIX}{token}")


def revoke_user_sessions(user_id: str, except_token: str | None = None) -> None:
    """이 회원의 세션을 모두 끊는다 (except_token은 유지)."""
    r = get_redis()
    key = f"{_USER_SESSIONS_PREFIX}{user_id}"
    for token in r.smembers(key):
        token = token.decode() if isinstance(token, bytes) else token
        if token != except_token:
            r.delete(f"{_SESSION_KEY_PREFIX}{token}")
            r.srem(key, token)
