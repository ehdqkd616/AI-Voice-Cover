import uuid

from sqlalchemy.orm import Session

from common.db.models import Job
from common.ids import new_id
from common.redis_client import get_redis

# Rough ETA table (seconds). "cover" is the only job type in this app — a
# single rough end-to-end estimate is good enough until the pipeline stages
# are broken out with their own telemetry.
ETA_SEC = {
    "cover": 240,
}

# Maps a Job.stage value to the Celery queue that stage's task runs on, so
# queue_position() can report a meaningful backlog for wherever the job
# currently sits in the pipeline (ingest -> separate -> convert -> mix).
QUEUE_NAME = {
    "ingest": "download",
    "separate": "separate",
    "convert": "convert",
    "mix": "dsp",
}


def create_job(
    db: Session,
    job_type: str,
    input_media: str | None,
    params: dict,
    user_id: uuid.UUID | None = None,
    stage: str = "ingest",
) -> Job:
    job = Job(
        id=new_id("job"),
        type=job_type,
        stage=stage,
        status="queued",
        input_media=input_media,
        params=params,
        user_id=user_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def queue_position(stage: str) -> int:
    queue = QUEUE_NAME.get(stage, "dsp")
    return get_redis().llen(queue)
