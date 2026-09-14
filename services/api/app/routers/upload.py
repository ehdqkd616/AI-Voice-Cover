import os
import tempfile

import magic
from fastapi import APIRouter, Depends, UploadFile

from common.cache import content_hash
from common.config import get_settings
from common.db.models import User
from common.ffprobe import ProbeError, probe
from common.media_registry import register_media
from common.storage import object_exists, upload_file

from ..deps import require_user
from ..errors import ApiError
from ..schemas.media import UploadResponse

router = APIRouter()

ALLOWED_MIME_EXT = {
    "audio/mpeg": "mp3",
    "audio/x-wav": "wav",
    "audio/wav": "wav",
    "audio/vnd.wave": "wav",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
}


@router.post("", response_model=UploadResponse)
async def upload(file: UploadFile, current_user: User = Depends(require_user)) -> UploadResponse:
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    fd, tmp_path = tempfile.mkstemp(prefix="up_")
    size = 0
    try:
        with os.fdopen(fd, "wb") as tmp:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise ApiError(
                        "FILE_TOO_LARGE",
                        f"파일이 {settings.max_upload_mb}MB 제한을 초과했습니다.",
                        {"max_mb": settings.max_upload_mb},
                    )
                tmp.write(chunk)

        # Magic-byte sniffing, not the client-supplied extension/Content-Type (§14.2).
        detected_mime = magic.from_file(tmp_path, mime=True)
        ext = ALLOWED_MIME_EXT.get(detected_mime)
        if not ext:
            raise ApiError(
                "UNSUPPORTED_FORMAT",
                "지원하지 않는 파일 형식입니다. MP3/WAV/M4A/FLAC만 업로드할 수 있습니다.",
                {"detected_mime": detected_mime},
            )

        try:
            meta = probe(tmp_path)
        except ProbeError as exc:
            raise ApiError("UNSUPPORTED_FORMAT", "파일을 디코딩할 수 없습니다.", {"reason": str(exc)})

        if not meta["has_audio"]:
            raise ApiError("UNSUPPORTED_FORMAT", "오디오 트랙을 찾을 수 없습니다.")
        if meta["duration_sec"] > settings.max_upload_duration_sec:
            raise ApiError(
                "FILE_TOO_LARGE",
                f"{settings.max_upload_duration_sec // 60}분을 초과하는 파일은 업로드할 수 없습니다.",
                {"duration_sec": meta["duration_sec"], "max_sec": settings.max_upload_duration_sec},
            )

        file_hash = content_hash(tmp_path)
        storage_key = f"uploads/{file_hash}.{ext}"
        if not object_exists(storage_key):
            upload_file(tmp_path, storage_key, detected_mime)

        title = os.path.splitext(file.filename or "")[0] or None
        media_id = register_media(
            kind="source",
            source_type="upload",
            parent_id=None,
            content_hash=file_hash,
            storage_key=storage_key,
            mime_type=detected_mime,
            size_bytes=size,
            duration_sec=meta["duration_sec"],
            sample_rate=meta["sample_rate"],
            channels=meta["channels"],
            title=title,
            lineage={"op": "upload"},
            user_id=current_user.id,
        )

        return UploadResponse(
            media_id=media_id, title=title, duration_sec=meta["duration_sec"], content_hash=file_hash
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
