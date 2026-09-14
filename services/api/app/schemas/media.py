from pydantic import BaseModel


class MediaUrlResponse(BaseModel):
    media_id: str
    url: str
    expires_in_sec: int


class UploadResponse(BaseModel):
    media_id: str
    title: str | None
    duration_sec: float | None
    content_hash: str
