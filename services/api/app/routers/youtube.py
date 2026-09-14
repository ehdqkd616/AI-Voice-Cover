from fastapi import APIRouter, Depends

from common.cache import L1_TTL, cache_get, cache_set, l1_key
from common.config import get_settings
from common.youtube_url import extract_video_id, normalize_youtube_url
from common.ytdlp import fetch_info

from ..deps import require_user
from ..errors import ApiError
from ..schemas.youtube import YoutubeInfoRequest, YoutubeInfoResponse

router = APIRouter()


@router.post("/info", response_model=YoutubeInfoResponse, dependencies=[Depends(require_user)])
def get_info(body: YoutubeInfoRequest) -> YoutubeInfoResponse:
    """Preview-only lookup — no /extract here. This app doesn't ingest the
    youtube audio until the cover pipeline itself runs (tasks.cover_ingest_youtube,
    owned by the workers team); this endpoint just powers the "confirm this is
    the right video" step in the UI before the user clicks Generate."""
    settings = get_settings()
    normalized = normalize_youtube_url(body.url)
    if not normalized:
        raise ApiError("INVALID_URL", "유효한 유튜브 URL이 아닙니다.")

    video_id = extract_video_id(normalized)
    cached = cache_get(l1_key(video_id, "info", "meta"))
    if cached:
        return YoutubeInfoResponse(**cached, cached=True)

    try:
        info = fetch_info(normalized)
    except Exception as exc:  # yt-dlp failure surfaces as retryable extraction error
        raise ApiError("EXTRACTION_FAILED", "유튜브 정보를 가져오지 못했습니다.", {"reason": str(exc)})

    if info.get("is_live"):
        raise ApiError("LIVE_STREAM_UNSUPPORTED", "라이브 스트림은 처리할 수 없습니다.")

    duration = int(info.get("duration") or 0)
    if duration > settings.max_youtube_duration_sec:
        raise ApiError(
            "VIDEO_TOO_LONG",
            f"{settings.max_youtube_duration_sec // 60}분을 초과하는 영상은 처리할 수 없습니다.",
            {"duration_sec": duration, "max_sec": settings.max_youtube_duration_sec},
        )

    payload = {
        "video_id": video_id,
        "title": info.get("title") or "",
        "channel": info.get("channel") or info.get("uploader") or "",
        "duration_sec": duration,
        "thumbnail": info.get("thumbnail"),
    }
    cache_set(l1_key(video_id, "info", "meta"), payload, L1_TTL)
    return YoutubeInfoResponse(**payload, cached=False)
