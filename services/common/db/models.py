import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    REAL,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Media(Base):
    __tablename__ = "media"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # med_xxxxx
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # source | stem | processed
    source_type: Mapped[str] = mapped_column(Text, nullable=False)  # youtube | upload | derived
    parent_id: Mapped[str | None] = mapped_column(Text, ForeignKey("media.id", ondelete="CASCADE"))

    content_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_sec: Mapped[float | None] = mapped_column(Numeric(10, 3))
    sample_rate: Mapped[int | None] = mapped_column()
    channels: Mapped[int | None] = mapped_column(SmallInteger)

    yt_video_id: Mapped[str | None] = mapped_column(Text, index=True)
    title: Mapped[str | None] = mapped_column(Text)
    artist: Mapped[str | None] = mapped_column(Text)

    lineage: Mapped[dict] = mapped_column(JSONB, server_default="{}")

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # job_xxxxx
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)  # "cover" (only type in this app)
    # ingest -> separate -> convert -> mix -> done (upload path skips straight to "separate")
    stage: Mapped[str] = mapped_column(Text, nullable=False, default="ingest")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    input_media: Mapped[str | None] = mapped_column(Text, ForeignKey("media.id", ondelete="SET NULL"))
    params: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    output_media: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    progress: Mapped[float] = mapped_column(REAL, default=0)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(default=0)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VoiceModel(Base):
    __tablename__ = "voice_models"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # vm_xxxxx
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    weight_filename: Mapped[str] = mapped_column(Text, nullable=False)  # filename under RVC_WEIGHT_ROOT
    index_filename: Mapped[str | None] = mapped_column(Text)  # filename under RVC_INDEX_ROOT, or NULL
    version: Mapped[str] = mapped_column(Text, nullable=False)  # "v1" | "v2"
    sample_rate: Mapped[int] = mapped_column(nullable=False)
    has_f0: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    speaker_id: Mapped[int] = mapped_column(nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    # "auto_high" | "auto_low" | "manual" | "unpaired" — set by tools/import_voice_models.py
    # or the admin upload/re-pair endpoints, surfaced in the admin UI as a review hint.
    pairing_confidence: Mapped[str] = mapped_column(Text, default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UsageCounter(Base):
    __tablename__ = "usage_counters"

    subject: Mapped[str] = mapped_column(Text, primary_key=True)  # user:{uuid} | ip:{hash}
    window_date: Mapped[datetime] = mapped_column(Date, primary_key=True)
    downloads: Mapped[int] = mapped_column(default=0)
    separations: Mapped[int] = mapped_column(default=0)
    gpu_seconds: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
