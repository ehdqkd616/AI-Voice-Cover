from datetime import datetime

from pydantic import BaseModel


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str
    queue_position: int | None = None
    eta_sec: int | None = None
    cached: bool = False


class JobStatusResponse(BaseModel):
    job_id: str
    type: str
    stage: str
    status: str
    progress: float
    output_media: list[str] | None = None
    error_code: str | None = None
    error_message: str | None = None
    cache_hit: bool
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
