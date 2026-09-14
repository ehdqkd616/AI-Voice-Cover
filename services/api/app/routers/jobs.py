import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from common.db.models import Job
from common.db.session import SessionLocal
from common.redis_client import get_redis

from ..errors import ApiError
from ..schemas.jobs import JobStatusResponse

router = APIRouter()


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise ApiError("NOT_FOUND", "작업을 찾을 수 없습니다.", {"job_id": job_id})
        return JobStatusResponse(
            job_id=job.id,
            type=job.type,
            stage=job.stage,
            status=job.status,
            progress=job.progress,
            output_media=job.output_media,
            error_code=job.error_code,
            error_message=job.error_message,
            cache_hit=job.cache_hit,
            queued_at=job.queued_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )
    finally:
        db.close()


@router.get("/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    """§7.2 SSE progress stream — subscribes to the job's Redis Pub/Sub channel
    that every worker task publishes to via `common.cache.publish_progress`."""

    async def event_stream():
        r = get_redis()
        pubsub = r.pubsub()
        pubsub.subscribe(f"progress:{job_id}")
        try:
            # Emit current state immediately so a late subscriber isn't stuck waiting.
            db = SessionLocal()
            try:
                job = db.get(Job, job_id)
                if job and job.status in ("succeeded", "failed"):
                    event = "complete" if job.status == "succeeded" else "error"
                    # Must match the live pub/sub shape from job_lifecycle.mark_succeeded
                    # ({"media_id": m} objects) — JobProgress.tsx reads o.media_id off each
                    # entry, so a bare string here silently produced `outputs: [undefined]`.
                    payload = {
                        "status": job.status,
                        "outputs": [{"media_id": m} for m in (job.output_media or [])],
                    }
                    if job.status == "failed":
                        payload["code"] = job.error_code
                        payload["message"] = job.error_message
                    yield f"event: {event}\ndata: {json.dumps(payload)}\n\n"
                    return
            finally:
                db.close()

            while True:
                # get_message() is a blocking redis-py call — run it off the event
                # loop thread so one open SSE stream doesn't stall every other request.
                message = await asyncio.to_thread(pubsub.get_message, timeout=15)
                if message and message["type"] == "message":
                    payload = json.loads(message["data"])
                    event = payload.pop("event", "progress")
                    yield f"event: {event}\ndata: {json.dumps(payload)}\n\n"
                    if event in ("complete", "error"):
                        return
                else:
                    yield ": keepalive\n\n"
        finally:
            pubsub.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
