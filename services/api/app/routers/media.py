import re
from datetime import timedelta

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from common.db.models import Media
from common.db.session import SessionLocal
from common.storage import _content_disposition, delete_object, get_object_stream, presigned_get_url

from ..errors import ApiError
from ..schemas.media import MediaUrlResponse

router = APIRouter()

PRESIGN_EXPIRY = timedelta(hours=1)

EXT_BY_MIME = {
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/vnd.wave": "wav",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "video/mp4": "mp4",
}

STEM_LABEL_EN = {"vocals": "Vocals", "instrumental": "Instrumental", "other": "Instrumental", "drums": "Drums", "bass": "Bass"}


def _extension(media: Media) -> str:
    if media.mime_type in EXT_BY_MIME:
        return EXT_BY_MIME[media.mime_type]
    if "." in media.storage_key:
        return media.storage_key.rsplit(".", 1)[-1]
    return "bin"


def _download_filename(media: Media) -> str:
    """제목 + 파이프라인의 어떤 단계를 거쳤는지(lineage.op) 반영한, 직관적으로
    읽히는 파일명. 최종 결과물(cover_mix)은 "{title} - Cover ({voice}).{ext}"
    형태로, 커버 다운로드 버튼을 눌렀을 때 바로 알아볼 수 있게 한다."""
    base = re.sub(r'[\\/:*?"<>|]', "_", (media.title or media.id)).strip() or media.id
    lineage = media.lineage or {}
    op = lineage.get("op")
    ext = _extension(media)

    if op == "separate":
        stem_label = STEM_LABEL_EN.get(lineage.get("stem"), lineage.get("stem", "stem"))
        return f"{base} - {stem_label}.{ext}"

    if op == "rvc_convert":
        voice_model_name = lineage.get("voice_model_name")
        if voice_model_name:
            return f"{base} - Vocals ({voice_model_name}).{ext}"
        return f"{base} - Vocals (Converted).{ext}"

    if op == "cover_mix":
        voice_model_name = lineage.get("voice_model_name")
        if voice_model_name:
            return f"{base} - Cover ({voice_model_name}).{ext}"
        return f"{base} - Cover.{ext}"

    return f"{base}.{ext}"


def _get_media_or_404(db, media_id: str) -> Media:
    media = db.get(Media, media_id)
    if not media:
        raise ApiError("NOT_FOUND", "미디어를 찾을 수 없습니다.", {"media_id": media_id})
    return media


def _collect_descendants(db, media_id: str) -> list[Media]:
    """분리/변환/믹스로 파생된 모든 하위 미디어를 재귀적으로 모은다 — DB 행은
    parent_id의 ON DELETE CASCADE가 알아서 지우지만, S3 오브젝트는 그 전에
    각자의 storage_key를 알아야 지울 수 있어서 삭제 전에 미리 훑어둔다."""
    found: list[Media] = []
    frontier = [media_id]
    while frontier:
        children = db.execute(select(Media).where(Media.parent_id.in_(frontier))).scalars().all()
        if not children:
            break
        found.extend(children)
        frontier = [c.id for c in children]
    return found


@router.get("/{media_id}/url", response_model=MediaUrlResponse)
def get_media_url(media_id: str) -> MediaUrlResponse:
    """스트리밍/재생용 URL — 브라우저가 inline으로 재생할 수 있어야 하므로
    다운로드 강제(Content-Disposition)를 걸지 않는다."""
    db = SessionLocal()
    try:
        media = _get_media_or_404(db, media_id)
        url = presigned_get_url(media.storage_key, PRESIGN_EXPIRY)
        return MediaUrlResponse(media_id=media_id, url=url, expires_in_sec=int(PRESIGN_EXPIRY.total_seconds()))
    finally:
        db.close()


@router.get("/{media_id}/download", response_model=MediaUrlResponse)
def get_media_download_url(media_id: str) -> MediaUrlResponse:
    """다운로드 버튼 전용 — response-content-disposition을 실어 보내 브라우저가
    재생 대신 바로 저장하도록 강제한다 (S3/MinIO의 GetObject 오버라이드 파라미터라
    바이트를 우리 API로 프록시할 필요 없이 presigned URL 하나로 해결된다)."""
    db = SessionLocal()
    try:
        media = _get_media_or_404(db, media_id)
        filename = _download_filename(media)
        url = presigned_get_url(media.storage_key, PRESIGN_EXPIRY, download_filename=filename)
        return MediaUrlResponse(media_id=media_id, url=url, expires_in_sec=int(PRESIGN_EXPIRY.total_seconds()))
    finally:
        db.close()


def _proxy_stream(media: Media, request: Request, disposition_filename: str | None) -> StreamingResponse:
    """Shared by /stream and /file — passes the browser's Range header
    through to MinIO so <audio> seeking works (jumping to the middle of a
    4-minute cover shouldn't re-download the first 3 minutes to get there),
    and mirrors it back as a 206 Partial Content response when honored."""
    result = get_object_stream(media.storage_key, request.headers.get("range"))
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(result["content_length"])}
    status_code = 200
    if result["content_range"]:
        headers["Content-Range"] = result["content_range"]
        status_code = 206
    if disposition_filename:
        headers["Content-Disposition"] = _content_disposition(disposition_filename)
    return StreamingResponse(
        result["body"].iter_chunks(),
        media_type=result["content_type"] or media.mime_type,
        headers=headers,
        status_code=status_code,
    )


@router.get("/{media_id}/stream")
def stream_media(media_id: str, request: Request) -> StreamingResponse:
    """Inline playback, proxied through the API instead of a presigned URL —
    see get_object_stream()'s docstring for why. Used by <audio src>, which
    (like /url) sends the session cookie automatically since it's a same-
    origin request through Caddy's /api/* proxy."""
    db = SessionLocal()
    try:
        media = _get_media_or_404(db, media_id)
        return _proxy_stream(media, request, disposition_filename=None)
    finally:
        db.close()


@router.get("/{media_id}/file")
def download_media_file(media_id: str, request: Request) -> StreamingResponse:
    """Forced-download counterpart to /stream — same proxying, with
    Content-Disposition: attachment so the browser saves instead of playing."""
    db = SessionLocal()
    try:
        media = _get_media_or_404(db, media_id)
        return _proxy_stream(media, request, disposition_filename=_download_filename(media))
    finally:
        db.close()


@router.delete("/{media_id}")
def delete_media(media_id: str) -> dict:
    """소스 미디어 하나를 지우면 그걸로 만든 스템·변환·믹스 결과물까지 전부 같이
    지운다 (media.parent_id의 ON DELETE CASCADE + 여기서 S3 오브젝트 정리)."""
    db = SessionLocal()
    try:
        media = _get_media_or_404(db, media_id)
        descendants = _collect_descendants(db, media_id)
        for child in descendants:
            delete_object(child.storage_key)
        delete_object(media.storage_key)
        db.delete(media)
        db.commit()
        return {"deleted": media_id, "cascaded": len(descendants)}
    finally:
        db.close()
