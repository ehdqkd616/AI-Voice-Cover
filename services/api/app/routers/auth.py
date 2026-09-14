from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from common.db.models import User
from common.db.session import SessionLocal

from ..deps import get_current_user
from ..errors import ApiError
from ..schemas.auth import LoginRequest, MeResponse, SignupRequest, UserResponse
from ..security import hash_password, verify_password
from ..session_store import SESSION_COOKIE_NAME, SESSION_TTL_SEC, create_session, delete_session

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


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        is_approved=user.is_approved,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


@router.post("/signup", response_model=UserResponse)
def signup(body: SignupRequest) -> UserResponse:
    """가입만 해두고 세션은 만들지 않는다 — 관리자 승인 전에는 로그인할 수 없다."""
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
        if existing:
            raise ApiError("EMAIL_TAKEN", "이미 가입된 이메일입니다.", {"email": body.email})
        user = User(email=body.email, password_hash=hash_password(body.password))
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    return _to_user_response(user)


@router.post("/login", response_model=UserResponse)
def login(body: LoginRequest, response: Response) -> UserResponse:
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
        if not user or not verify_password(body.password, user.password_hash):
            raise ApiError("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다.")
        if not user.is_approved:
            raise ApiError("PENDING_APPROVAL", "관리자 승인 대기 중입니다.")
    finally:
        db.close()

    _set_session_cookie(response, create_session(str(user.id)))
    return _to_user_response(user)


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        delete_session(token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"logged_out": True}


@router.get("/me", response_model=MeResponse)
def me(current_user: User | None = Depends(get_current_user)) -> MeResponse:
    return MeResponse(user=_to_user_response(current_user) if current_user else None)
