from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from common.config import get_settings
from common.db.models import User
from common.db.session import SessionLocal
from common.storage import ensure_bucket
from .errors import ApiError, api_error_handler
from .routers import admin, auth, cover, jobs, library, media, upload, voice_models, youtube
from .security import hash_password

settings = get_settings()

app = FastAPI(title="AI Voice Cover API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(voice_models.router, prefix="/api/v1/voice-models", tags=["voice-models"])
app.include_router(
    voice_models.admin_router, prefix="/api/v1/admin/voice-models", tags=["admin", "voice-models"]
)
app.include_router(youtube.router, prefix="/api/v1/youtube", tags=["youtube"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(cover.router, prefix="/api/v1/cover", tags=["cover"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(media.router, prefix="/api/v1/media", tags=["media"])
app.include_router(library.router, prefix="/api/v1/library", tags=["library"])


def _bootstrap_admin() -> None:
    """Creates the one approved admin from ADMIN_EMAIL/ADMIN_PASSWORD (.env) if it
    doesn't exist yet — the only way to get a first admin without a DB console,
    since signup alone leaves every account unapproved."""
    email, password = settings.admin_email, settings.admin_password
    if not email or not password:
        return
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            return
        db.add(
            User(email=email, password_hash=hash_password(password), is_approved=True, is_admin=True)
        )
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    ensure_bucket()
    _bootstrap_admin()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
