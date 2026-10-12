"""회원 공통 로직 — 모든 프로젝트 공통 규칙(아이디 가입·승인제·admin 계정)."""

import secrets
import string

from fastapi import Request
from sqlalchemy import select

from common.config import get_settings
from common.db.models import AuditLog, User
from common.db.session import SessionLocal
from common.redis_client import get_redis

from .errors import ApiError
from .security import hash_password, verify_password
from .session_store import revoke_user_sessions

# 모든 프로젝트 공통 관리자 아이디 — 비밀번호는 .env의 ADMIN_PASSWORD로 관리
ADMIN_USERNAME = "admin"

STATUS_ERRORS = {
    "pending": ("ACCOUNT_PENDING", "관리자 승인 대기 중입니다. 승인 후 이용할 수 있습니다."),
    "rejected": ("ACCOUNT_REJECTED", "가입이 거절되었습니다."),
    "suspended": ("ACCOUNT_SUSPENDED", "이용이 정지된 계정입니다. 관리자에게 문의하세요."),
}

LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_SEC = 15 * 60


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def audit(db, action: str, *, actor_id=None, target_id=None, detail: dict | None = None, ip: str | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target_id=str(target_id) if target_id else None, detail=detail, ip=ip))


# --- 로그인 시도 제한 (아이디·IP별 5회 실패 시 15분 잠금) ---------------------------

def _fail_keys(username: str, ip: str | None) -> list[str]:
    return [f"loginfail:user:{username}"] + ([f"loginfail:ip:{ip}"] if ip else [])


def check_login_locked(username: str, ip: str | None) -> None:
    r = get_redis()
    for key in _fail_keys(username, ip):
        if int(r.get(key) or 0) >= LOGIN_MAX_FAILURES:
            minutes = (max(r.ttl(key), 1) + 59) // 60
            raise ApiError("LOGIN_LOCKED", f"로그인 시도가 너무 많습니다. 약 {minutes}분 후 다시 시도하세요.")


def record_login_failure(username: str, ip: str | None) -> None:
    r = get_redis()
    for key in _fail_keys(username, ip):
        if r.incr(key) == 1:
            r.expire(key, LOGIN_LOCK_SEC)


def clear_login_failures(username: str) -> None:
    get_redis().delete(f"loginfail:user:{username}")


def temp_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


def is_managed_admin(user: User) -> bool:
    """비밀번호를 .env의 ADMIN_PASSWORD로 관리하는 공통 관리자 계정(admin)인지"""
    return user.username == ADMIN_USERNAME


def ensure_admin() -> str | None:
    """기동할 때마다 .env의 ADMIN_PASSWORD로 공통 관리자 계정 admin을 맞춘다.
    없으면 만들고, 있으면 관리자·승인 상태와 비밀번호를 .env 값으로 되돌린다 — 비밀번호는 .env가 기준."""
    password = get_settings().admin_password
    if not password:
        return None
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.username == ADMIN_USERNAME)).scalar_one_or_none()
        if user is None:
            from datetime import datetime, timezone

            db.add(User(username=ADMIN_USERNAME, name="관리자", password_hash=hash_password(password),
                        status="approved", is_admin=True, approved_at=datetime.now(timezone.utc)))
            db.commit()
            return "created"
        same_password = verify_password(password, user.password_hash)
        if same_password and user.is_admin and user.status == "approved":
            return None
        user.is_admin, user.status = True, "approved"
        if not same_password:
            user.password_hash = hash_password(password)
            revoke_user_sessions(str(user.id))  # 예전 비밀번호로 만든 세션 종료
        db.commit()
        return "synced"
    finally:
        db.close()
