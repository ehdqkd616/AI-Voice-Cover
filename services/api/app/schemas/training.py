from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TrainingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=200)
    media_ids: list[str] = Field(min_length=1, max_length=50)
    # Isolate the vocal with Demucs first, so full songs work as training data.
    auto_vocal: bool = True
    epochs: int = Field(default=200, ge=10, le=1000)
    batch_size: int = Field(default=2, ge=1, le=16)
    sample_rate: Literal["40k", "48k"] = "40k"


class TrainingJobResponse(BaseModel):
    job_id: str
    name: str
    description: str | None
    status: str
    stage: str
    progress: float
    epochs: int
    current_epoch: int
    eta_sec: int | None
    sample_rate: str
    batch_size: int
    effective_batch_size: int | None
    auto_vocal: bool
    file_count: int
    dataset_seconds: float | None
    voice_model_id: str | None
    error_code: str | None
    error_message: str | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class TrainingLogResponse(BaseModel):
    stage: str
    lines: list[str]
