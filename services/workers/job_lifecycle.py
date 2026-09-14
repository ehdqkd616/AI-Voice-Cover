"""Job status transitions shared by every Celery task."""

from datetime import datetime, timezone

from common.cache import publish_progress
from common.db.models import Job
from common.db.session import session_scope
from common.media_registry import register_media  # noqa: F401 — re-exported for task modules

RETRYABLE_CODES = {"EXTRACTION_FAILED", "RATE_LIMITED", "QUEUE_FULL", "GPU_OOM"}
MAX_ATTEMPTS = 3
BACKOFF_SEC = [2, 8, 32]

# Job.stage -> (lo, hi) percent range. scaled_progress() maps a stage-local
# 0-100 percent into this range so the SSE progress bar moves monotonically
# across the whole ingest -> separate -> convert -> mix pipeline instead of
# resetting to 0 at the start of every stage.
STAGE_RANGE = {"ingest": (0, 10), "separate": (10, 45), "convert": (45, 80), "mix": (80, 100)}


def scaled_progress(stage: str, local_percent: float) -> float:
    lo, hi = STAGE_RANGE[stage]
    return lo + (hi - lo) * (local_percent / 100)


def mark_running(job_id: str) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)


def mark_progress(job_id: str, percent: float, stage: str) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        job.progress = percent
    publish_progress(job_id, {"stage": stage, "percent": percent})


def mark_succeeded(job_id: str, output_media: list[str], cache_hit: bool = False) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        job.status = "succeeded"
        job.output_media = output_media
        job.cache_hit = cache_hit
        job.progress = 100
        job.finished_at = datetime.now(timezone.utc)
        # A retried job (mark_failed on an earlier attempt, then a later
        # attempt succeeds) would otherwise keep showing its last failure's
        # code/message forever even though it ended in success.
        job.error_code = None
        job.error_message = None
    publish_progress(
        job_id,
        {
            "event": "complete",
            "status": "succeeded",
            "outputs": [{"media_id": m} for m in output_media],
        },
    )


def mark_failed(job_id: str, code: str, message: str, detail: dict | None = None) -> bool:
    """Returns True if the caller should retry (attempts remain and code is retryable)."""
    with session_scope() as db:
        job = db.get(Job, job_id)
        job.attempts += 1
        retryable = code in RETRYABLE_CODES and job.attempts < MAX_ATTEMPTS
        job.status = "queued" if retryable else "failed"
        job.error_code = code
        job.error_message = message
        attempts = job.attempts
    publish_progress(
        job_id,
        {
            "event": "error",
            "code": code,
            "message": message,
            "detail": detail or {},
            "retryable": retryable,
        },
    )
    return retryable


def advance_stage(job_id: str, next_stage: str, extra_params: dict, next_task: str, next_queue: str) -> None:
    """On a stage's success: merge its output into Job.params, move to the next
    stage, reset status to queued, and enqueue the next task — this app's
    alternative to a Celery chain/chord, so the DB row stays the single
    source of truth for stage/progress/error (matches mark_* above)."""
    with session_scope() as db:
        job = db.get(Job, job_id)
        job.params = {**job.params, **extra_params}
        job.stage = next_stage
        job.status = "queued"

    from workers.celery_app import app

    app.send_task(next_task, args=[job_id], queue=next_queue)
