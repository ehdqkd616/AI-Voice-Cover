"""Shared `media` table writer — used by both the API (uploads) and workers."""

import uuid
from datetime import datetime, timedelta, timezone

from .config import get_settings
from .db.models import Media
from .db.session import session_scope
from .ids import new_id


def register_media(
    *,
    media_id: str | None = None,
    kind: str,
    source_type: str,
    parent_id: str | None,
    content_hash: str,
    storage_key: str,
    mime_type: str,
    size_bytes: int,
    duration_sec: float | None = None,
    sample_rate: int | None = None,
    channels: int | None = None,
    yt_video_id: str | None = None,
    title: str | None = None,
    artist: str | None = None,
    lineage: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    media_id = media_id or new_id("med")
    ttl = timedelta(hours=get_settings().media_ttl_hours)
    with session_scope() as db:
        media = Media(
            id=media_id,
            user_id=user_id,
            kind=kind,
            source_type=source_type,
            parent_id=parent_id,
            content_hash=content_hash,
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            channels=channels,
            yt_video_id=yt_video_id,
            title=title,
            artist=artist,
            lineage=lineage or {},
            expires_at=datetime.now(timezone.utc) + ttl,
        )
        db.merge(media)
    return media_id
