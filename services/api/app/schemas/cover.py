from typing import Literal

from pydantic import BaseModel, Field


class CoverRequest(BaseModel):
    media_id: str | None = None
    youtube_url: str | None = None

    voice_model_id: str

    f0_up_key: int = Field(default=0, ge=-24, le=24)
    f0_method: Literal["pm", "rmvpe", "fcpe"] = "rmvpe"
    index_rate: float = Field(default=0.75, ge=0.0, le=1.0)
    protect: float = Field(default=0.33, ge=0.0, le=0.5)
    rms_mix_rate: float = Field(default=0.25, ge=0.0, le=1.0)
    output_format: Literal["mp3-320", "wav"] = "mp3-320"
    vocal_gain_db: float = 0
    quality: Literal["fast", "high"] = "fast"
    # Independent of f0_up_key (which only retunes the RVC-converted vocal) —
    # this transposes the instrumental/MR track itself, tempo-preserved.
    instrumental_pitch: int = Field(default=0, ge=-24, le=24)
