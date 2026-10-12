from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# 아이디: 영문/숫자/_/- 3~32자 (모든 프로젝트 공통 규칙)
USERNAME_PATTERN = r"^[A-Za-z0-9_-]{3,32}$"


class SignupRequest(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=72)  # bcrypt caps input at 72 bytes
    signup_note: str | None = Field(default=None, max_length=1000)
    agree_terms: bool
    agree_privacy: bool

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("이름을 입력하세요.")
        return v


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class UserResponse(BaseModel):
    id: str
    username: str
    name: str
    status: str
    is_approved: bool
    is_admin: bool
    created_at: datetime
    password_managed: bool = False


class MeResponse(BaseModel):
    user: UserResponse | None


class AdminUserResponse(UserResponse):
    signup_note: str | None
    reject_reason: str | None
    approved_at: datetime | None
    last_login_at: datetime | None
