from pydantic import BaseModel


class YoutubeInfoRequest(BaseModel):
    url: str


class YoutubeInfoResponse(BaseModel):
    video_id: str
    title: str
    channel: str
    duration_sec: int
    thumbnail: str | None = None
    cached: bool
