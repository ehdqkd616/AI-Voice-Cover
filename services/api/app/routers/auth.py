from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import func, select

from common.db.models import User
from common.db.session import SessionLocal

from ..accounts import (
    STATUS_ERRORS, audit, check_login_locked, clear_login_failures, client_ip, is_managed_admin, record_login_failure,
)
from ..deps import get_current_user, require_user
from ..errors import ApiError
from ..notify import send_signup_notification
from ..schemas.auth import LoginRequest, MeResponse, PasswordChangeRequest, SignupRequest, UserResponse
from ..security import hash_password, verify_password
from ..session_store import (
    SESSION_COOKIE_NAME, SESSION_TTL_SEC, create_session, delete_session, revoke_user_sessions,
)

router = APIRouter()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SEC,
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
    )


def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        name=user.name,
        status=user.status,
        is_approved=user.is_approved,
        is_admin=user.is_admin,
        created_at=user.created_at,
        password_managed=is_managed_admin(user),
    )


@router.post("/signup", status_code=201)
def signup(body: SignupRequest, request: Request, background_tasks: BackgroundTasks) -> dict:
    """가입만 해두고 세션은 만들지 않는다 — 관리자 승인 전에는 로그인할 수 없다."""
    if not (body.agree_terms and body.agree_privacy):
        raise ApiError("VALIDATION_ERROR", "이용약관과 개인정보 처리방침에 동의해 주세요.")
    username = body.username.lower()
    note = (body.signup_note or "").strip() or None
    db = SessionLocal()
    try:
        if db.execute(select(User.id).where(func.lower(User.username) == username)).first():
            raise ApiError("USERNAME_TAKEN", "이미 사용 중인 아이디입니다.", {"username": username})
        user = User(username=username, name=body.name, signup_note=note,
                    password_hash=hash_password(body.password), status="pending")
        db.add(user)
        db.flush()
        audit(db, "user.signup", actor_id=user.id, target_id=user.id, ip=client_ip(request))
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    # 응답을 보낸 뒤 발송 — SMTP가 느리거나 실패해도 가입은 그대로 성공한다.
    background_tasks.add_task(send_signup_notification, user.username, user.name, note, user.created_at)
    return {"status": "pending", "message": "가입 신청이 완료되었습니다. 관리자 승인 후 이용할 수 있습니다."}


@router.post("/login", response_model=UserResponse)
def login(body: LoginRequest, request: Request, response: Response) -> UserResponse:
    # 아이디 형식은 검사하지 않는다 — 예전 계정은 이메일이 아이디다
    username = body.username.strip().lower()
    ip = client_ip(request)
    check_login_locked(username, ip)
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(func.lower(User.username) == username)).scalar_one_or_none()
        if not user or not verify_password(body.password, user.password_hash):
            record_login_failure(username, ip)
            audit(db, "login.failure", actor_id=user.id if user else None, target_id=user.id if user else None,
                  detail={"username": username[:64]}, ip=ip)
            db.commit()
            raise ApiError("INVALID_CREDENTIALS", "아이디 또는 비밀번호가 올바르지 않습니다.")
        clear_login_failures(username)
        # 비밀번호가 맞을 때만 계정 상태를 알려준다
        if user.status != "approved":
            code, message = STATUS_ERRORS[user.status]
            audit(db, "login.blocked", actor_id=user.id, target_id=user.id, detail={"status": user.status}, ip=ip)
            db.commit()
            raise ApiError(code, message, {"reason": user.reject_reason} if user.status == "rejected" and user.reject_reason else None)
        user.last_login_at = datetime.now(timezone.utc)
        audit(db, "login.success", actor_id=user.id, target_id=user.id, ip=ip)
        db.commit()
        db.refresh(user)
        result = to_user_response(user)
    finally:
        db.close()

    _set_session_cookie(response, create_session(result.id))
    return result


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        delete_session(token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"logged_out": True}


@router.get("/me", response_model=MeResponse)
def me(current_user: User | None = Depends(get_current_user)) -> MeResponse:
    return MeResponse(user=to_user_response(current_user) if current_user else None)


@router.patch("/password")
def change_password(body: PasswordChangeRequest, request: Request, current_user: User = Depends(require_user)) -> dict:
    if is_managed_admin(current_user):
        raise ApiError("ADMIN_PASSWORD_MANAGED", "관리자 비밀번호는 서버 .env의 ADMIN_PASSWORD로 관리합니다.")
    if not verify_password(body.current_password, current_user.password_hash):
        raise ApiError("INVALID_CREDENTIALS", "현재 비밀번호가 올바르지 않습니다.")
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        user.password_hash = hash_password(body.new_password)
        audit(db, "user.password_change", actor_id=user.id, target_id=user.id, ip=client_ip(request))
        db.commit()
    finally:
        db.close()
    # 다른 기기의 세션은 종료
    revoke_user_sessions(str(current_user.id), except_token=request.cookies.get(SESSION_COOKIE_NAME))
    return {"ok": True}
