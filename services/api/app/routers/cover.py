from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from common.celery_client import send_task
from common.db.models import Media, User, VoiceModel
from common.db.session import SessionLocal
from common.youtube_url import normalize_youtube_url

from ..deps import enforce_separate_quota, require_user
from ..errors import ApiError
from ..job_utils import ETA_SEC, create_job, queue_position
from ..schemas.cover import CoverRequest
from ..schemas.jobs import JobCreatedResponse

router = APIRouter()


def _conversion_params(body: CoverRequest) -> dict:
    return {
        "f0_up_key": body.f0_up_key,
        "f0_method": body.f0_method,
        "index_rate": body.index_rate,
        "protect": body.protect,
        "rms_mix_rate": body.rms_mix_rate,
        "output_format": body.output_format,
        "vocal_gain_db": body.vocal_gain_db,
        "quality": body.quality,
        "separation_engine": body.separation_engine,
        "instrumental_pitch": body.instrumental_pitch,
    }


@router.post("", response_model=JobCreatedResponse, dependencies=[Depends(enforce_separate_quota)])
def create_cover(body: CoverRequest, current_user: User = Depends(require_user)) -> JobCreatedResponse:
    """Kicks off the full cover pipeline. Exactly one of media_id/youtube_url
    selects the source; from there the two paths diverge only in which stage
    they start at and which task picks the job up — a youtube source still
    needs ingest (download + extract audio) before separation can run, while
    an already-uploaded media_id skips straight to separate."""
    if bool(body.media_id) == bool(body.youtube_url):
        raise ApiError(
            "VALIDATION_ERROR",
            "media_id와 youtube_url 중 정확히 하나만 지정해야 합니다.",
            {"media_id": body.media_id, "youtube_url": body.youtube_url},
        )

    db: Session = SessionLocal()
    try:
        voice_model = db.get(VoiceModel, body.voice_model_id)
        if not voice_model or not voice_model.is_active:
            raise ApiError(
                "NOT_FOUND", "음성 모델을 찾을 수 없습니다.", {"voice_model_id": body.voice_model_id}
            )

        params = _conversion_params(body)
        params["voice_model_id"] = voice_model.id
        params["voice_model_name"] = voice_model.name

        if body.youtube_url:
            normalized = normalize_youtube_url(body.youtube_url)
            if not normalized:
                raise ApiError("INVALID_URL", "유효한 유튜브 URL이 아닙니다.")
            params["source_type"] = "youtube"
            params["youtube_url"] = normalized
            job = create_job(db, "cover", None, params, user_id=current_user.id, stage="ingest")
        else:
            media = db.get(Media, body.media_id)
            if not media:
                raise ApiError("NOT_FOUND", "미디어를 찾을 수 없습니다.", {"media_id": body.media_id})
            params["source_type"] = "upload"
            params["media_id"] = body.media_id
            job = create_job(db, "cover", body.media_id, params, user_id=current_user.id, stage="separate")
    finally:
        db.close()

    if job.stage == "ingest":
        send_task("tasks.cover_ingest_youtube", args=[job.id], queue="download")
    elif body.separation_engine == "mdx_net":
        send_task("tasks.cover_separate_mdx", args=[job.id], queue="mdx")
    else:
        send_task("tasks.cover_separate", args=[job.id], queue="separate")

    return JobCreatedResponse(
        job_id=job.id,
        status="queued",
        queue_position=queue_position(job.stage),
        eta_sec=ETA_SEC["cover"],
        cached=False,
    )
