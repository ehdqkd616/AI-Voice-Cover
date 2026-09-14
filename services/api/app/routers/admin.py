from fastapi import APIRouter, Depends
from sqlalchemy import select

from common.db.models import User
from common.db.session import SessionLocal

from ..deps import require_admin
from ..errors import ApiError
from ..schemas.auth import UserResponse

router = APIRouter()


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        is_approved=user.is_approved,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


def _get_user(db, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise ApiError("NOT_FOUND", "사용자를 찾을 수 없습니다.", {"user_id": user_id})
    return user


@router.get("/users", response_model=list[UserResponse], dependencies=[Depends(require_admin)])
def list_users() -> list[UserResponse]:
    db = SessionLocal()
    try:
        users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
        return [_to_user_response(u) for u in users]
    finally:
        db.close()


@router.post("/users/{user_id}/approve", response_model=UserResponse)
def approve_user(user_id: str, current_user: User = Depends(require_admin)) -> UserResponse:
    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        user.is_approved = True
        db.commit()
        db.refresh(user)
        return _to_user_response(user)
    finally:
        db.close()


@router.post("/users/{user_id}/unapprove", response_model=UserResponse)
def unapprove_user(user_id: str, current_user: User = Depends(require_admin)) -> UserResponse:
    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        if user.id == current_user.id:
            raise ApiError("VALIDATION_ERROR", "본인 계정은 승인 취소할 수 없습니다.")
        user.is_approved = False
        db.commit()
        db.refresh(user)
        return _to_user_response(user)
    finally:
        db.close()


@router.delete("/users/{user_id}")
def delete_user(user_id: str, current_user: User = Depends(require_admin)) -> dict:
    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        if user.id == current_user.id:
            raise ApiError("VALIDATION_ERROR", "본인 계정은 삭제할 수 없습니다.")
        db.delete(user)
        db.commit()
        return {"deleted": user_id}
    finally:
        db.close()
