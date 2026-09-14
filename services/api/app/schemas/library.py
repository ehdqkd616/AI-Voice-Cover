from datetime import datetime

from pydantic import BaseModel


class LibraryItem(BaseModel):
    job_id: str
    media_id: str
    title: str | None
    artist: str | None
    voice_model_name: str | None
    source_type: str | None
    duration_sec: float | None
    output_format: str | None
    created_at: datetime
