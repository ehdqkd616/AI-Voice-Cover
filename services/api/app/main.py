import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from common.config import get_settings
from common.storage import ensure_bucket
from .accounts import ADMIN_USERNAME, ensure_admin
from .errors import ApiError, api_error_handler
from .routers import admin, auth, cover, jobs, library, media, training, upload, voice_models, youtube

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
app.include_router(training.router, prefix="/api/v1/training", tags=["training"])


@app.on_event("startup")
def on_startup() -> None:
    ensure_bucket()
    result = ensure_admin()
    if result:
        logging.getLogger(__name__).info("관리자 계정 %s: %s", "생성" if result == "created" else "동기화", ADMIN_USERNAME)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
