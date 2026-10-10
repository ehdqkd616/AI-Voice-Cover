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


class TrainingResumeRequest(BaseModel):
    # Epochs to add on top of the last saved checkpoint. Ignored when the job
    # has no checkpoint yet (it failed before training) — that reruns the
    # whole pipeline with the original epoch count.
    extra_epochs: int = Field(default=100, ge=1, le=1000)
    # None keeps the batch size that last worked (after any OOM fallback).
    batch_size: int | None = Field(default=None, ge=1, le=16)


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
    # Last epoch with a saved G/D checkpoint — where "이어서 학습" picks up.
    checkpoint_epoch: int | None
    # Experiment dir has a G/D checkpoint plus extracted features, so a resume
    # can skip straight to training. Without one, a resume of a failed job
    # reruns the whole pipeline instead.
    has_checkpoint: bool
    # The trained .pth exists and can be downloaded.
    has_model_file: bool
    resume_count: int


class TrainingLogResponse(BaseModel):
    stage: str
    lines: list[str]
