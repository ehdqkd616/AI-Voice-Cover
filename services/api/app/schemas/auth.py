from datetime import datetime

from pydantic import BaseModel, Field


# 아이디: 영문/숫자/_/- 3~32자 (모든 프로젝트 공통 규칙)
USERNAME_PATTERN = r"^[A-Za-z0-9_-]{3,32}$"


class SignupRequest(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=72)  # bcrypt caps input at 72 bytes


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    is_approved: bool
    is_admin: bool
    created_at: datetime


class MeResponse(BaseModel):
    user: UserResponse | None
