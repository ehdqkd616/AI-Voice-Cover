"""Voice-model training (admin only — trained models join the shared voice
model registry). The work happens in the worker's tasks.train_voice_model;
this router creates/inspects/cancels those jobs and serves their log tails
from ./data/training (mounted at settings.training_root)."""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from common.celery_client import send_task
from common.config import get_settings
from common.db.models import Job, Media, User, VoiceModel
from common.db.session import SessionLocal
from common.redis_client import get_redis

from ..deps import require_admin
from ..errors import ApiError
from ..job_utils import create_job
from ..schemas.training import TrainingJobResponse, TrainingLogResponse, TrainingRequest

router = APIRouter()

ACTIVE = ("queued", "running")
# Which log is worth showing while a job sits in each stage (files written by
# the vendored RVC scripts, plus prepare.log from tasks/train.py).
STAGE_LOG = {
    "prepare": "prepare.log",
    "preprocess": "preprocess.log",
    "extract": "extract_f0_feature.log",
    "train": "train.log",
    "index": "train_index.log",
}


def _cancel_key(job_id: str) -> str:
    return f"train:cancel:{job_id}"  # must match workers/tasks/train.py


def _to_response(job: Job) -> TrainingJobResponse:
    p = job.params or {}
    return TrainingJobResponse(
        job_id=job.id,
        name=p.get("name", ""),
        description=p.get("description"),
        status=job.status,
        stage=job.stage,
        progress=job.progress or 0,
        epochs=int(p.get("epochs", 0)),
        current_epoch=int(p.get("current_epoch") or 0),
        eta_sec=p.get("eta_sec"),
        sample_rate=p.get("sample_rate", "40k"),
        batch_size=int(p.get("batch_size", 0)),
        effective_batch_size=p.get("effective_batch_size"),
        auto_vocal=bool(p.get("auto_vocal", True)),
        file_count=len(p.get("media_ids", [])),
        dataset_seconds=p.get("dataset_seconds"),
        voice_model_id=p.get("voice_model_id"),
        error_code=job.error_code,
        error_message=job.error_message,
        queued_at=job.queued_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _get_train_job(db, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job or job.type != "train":
        raise ApiError("NOT_FOUND", "학습 작업을 찾을 수 없습니다.", {"job_id": job_id})
    return job


@router.post("", response_model=TrainingJobResponse)
def start_training(body: TrainingRequest, current_user: User = Depends(require_admin)) -> TrainingJobResponse:
    name = body.name.strip()
    db = SessionLocal()
    try:
        if db.execute(select(VoiceModel.id).where(VoiceModel.name == name)).first():
            raise ApiError("NAME_TAKEN", "같은 이름의 보이스 모델이 이미 있습니다.", {"name": name})
        in_flight = db.execute(select(Job).where(Job.type == "train", Job.status.in_(ACTIVE))).scalars().all()
        if any((j.params or {}).get("name") == name for j in in_flight):
            raise ApiError("NAME_TAKEN", "같은 이름으로 진행 중인 학습이 있습니다.", {"name": name})

        media_ids = list(dict.fromkeys(body.media_ids))
        found = {m.id for m in db.execute(select(Media).where(Media.id.in_(media_ids))).scalars()}
        missing = [m for m in media_ids if m not in found]
        if missing:
            raise ApiError("NOT_FOUND", "업로드한 음원 일부를 찾을 수 없습니다.", {"media_ids": missing})

        job = create_job(
            db,
            "train",
            media_ids[0],
            {
                "name": name,
                "description": body.description,
                "media_ids": media_ids,
                "auto_vocal": body.auto_vocal,
                "epochs": body.epochs,
                "batch_size": body.batch_size,
                "sample_rate": body.sample_rate,
            },
            user_id=current_user.id,
            stage="prepare",
        )
        # ASCII-only experiment dir name — the display name may be Korean.
        job.params = {**job.params, "exp_name": f"vc_{job.id.removeprefix('job_')}"}
        db.commit()
        db.refresh(job)
        response = _to_response(job)
    finally:
        db.close()

    send_task("tasks.train_voice_model", args=[response.job_id], queue="train")
    return response


@router.get("", response_model=list[TrainingJobResponse])
def list_training(current_user: User = Depends(require_admin)) -> list[TrainingJobResponse]:
    db = SessionLocal()
    try:
        jobs = db.execute(select(Job).where(Job.type == "train").order_by(Job.queued_at.desc())).scalars().all()
        return [_to_response(j) for j in jobs]
    finally:
        db.close()


@router.get("/{job_id}", response_model=TrainingJobResponse)
def get_training(job_id: str, current_user: User = Depends(require_admin)) -> TrainingJobResponse:
    db = SessionLocal()
    try:
        return _to_response(_get_train_job(db, job_id))
    finally:
        db.close()


@router.get("/{job_id}/log", response_model=TrainingLogResponse)
def training_log(
    job_id: str,
    lines: int = Query(default=200, ge=1, le=2000),
    current_user: User = Depends(require_admin),
) -> TrainingLogResponse:
    db = SessionLocal()
    try:
        job = _get_train_job(db, job_id)
        exp_name, stage = (job.params or {}).get("exp_name", ""), job.stage
    finally:
        db.close()

    path = Path(get_settings().training_root) / exp_name / STAGE_LOG.get(stage, "train.log")
    try:
        text = path.read_text(encoding="utf8", errors="replace")
    except FileNotFoundError:
        text = ""
    return TrainingLogResponse(stage=stage, lines=text.splitlines()[-lines:])


@router.post("/{job_id}/cancel", response_model=TrainingJobResponse)
def cancel_training(job_id: str, current_user: User = Depends(require_admin)) -> TrainingJobResponse:
    db = SessionLocal()
    try:
        job = _get_train_job(db, job_id)
        if job.status not in ACTIVE:
            return _to_response(job)
        # The worker polls this key between steps and while a script runs.
        get_redis().set(_cancel_key(job_id), "1", ex=60 * 60 * 24 * 7)
        if job.status == "queued":
            # Not picked up yet — show it as stopped right away; the worker
            # still sees the key and exits immediately when it reaches it.
            job.status = "failed"
            job.error_code = "CANCELLED"
            job.error_message = "학습을 중지했습니다."
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(job)
        return _to_response(job)
    finally:
        db.close()


@router.delete("/{job_id}")
def delete_training(job_id: str, current_user: User = Depends(require_admin)) -> dict:
    """Removes the job record and its experiment dir (dataset, checkpoints,
    logs). A model it already produced stays in the voice-model registry —
    delete that separately from /admin/models if wanted."""
    db = SessionLocal()
    try:
        job = _get_train_job(db, job_id)
        if job.status in ACTIVE:
            raise ApiError("TRAINING_ACTIVE", "진행 중인 학습은 먼저 중지해야 삭제할 수 있습니다.")
        exp_name = (job.params or {}).get("exp_name")
        db.delete(job)
        db.commit()
    finally:
        db.close()

    if exp_name:
        shutil.rmtree(Path(get_settings().training_root) / exp_name, ignore_errors=True)
    return {"deleted": job_id}
