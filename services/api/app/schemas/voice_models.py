from datetime import datetime

from pydantic import BaseModel


class VoiceModelResponse(BaseModel):
    """Public listing — internal filename/storage details are omitted."""

    id: str
    name: str
    description: str | None
    thumbnail_url: str | None
    version: str
    sample_rate: int
    has_f0: bool
    pairing_confidence: str


class VoiceModelAdminResponse(BaseModel):
    id: str
    name: str
    description: str | None
    thumbnail_url: str | None
    weight_filename: str
    index_filename: str | None
    version: str
    sample_rate: int
    has_f0: bool
    speaker_id: int
    pairing_confidence: str
    is_active: bool
    created_at: datetime


class VoiceModelUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    index_filename: str | None = None
    is_active: bool | None = None
