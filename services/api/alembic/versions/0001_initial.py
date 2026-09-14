"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-14

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "media",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Text(), sa.ForeignKey("media.id", ondelete="CASCADE")),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("duration_sec", sa.Numeric(10, 3)),
        sa.Column("sample_rate", sa.Integer()),
        sa.Column("channels", sa.SmallInteger()),
        sa.Column("yt_video_id", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("artist", sa.Text()),
        sa.Column("lineage", postgresql.JSONB(), server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_media_hash", "media", ["content_hash"])
    op.create_index("idx_media_expires", "media", ["expires_at"])
    op.create_index("idx_media_user", "media", ["user_id", "created_at"])
    op.create_index(
        "idx_media_ytid", "media", ["yt_video_id"], postgresql_where=sa.text("yt_video_id IS NOT NULL")
    )

    op.create_table(
        "voice_models",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("weight_filename", sa.Text(), nullable=False),
        sa.Column("index_filename", sa.Text()),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("has_f0", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("speaker_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text()),
        sa.Column("thumbnail_url", sa.Text()),
        sa.Column("pairing_confidence", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_voice_models_active", "voice_models", ["is_active"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False, server_default="ingest"),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("input_media", sa.Text(), sa.ForeignKey("media.id", ondelete="SET NULL")),
        sa.Column("params", postgresql.JSONB(), server_default="{}"),
        sa.Column("output_media", postgresql.ARRAY(sa.Text())),
        sa.Column("progress", sa.REAL(), server_default="0"),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("cache_hit", sa.Boolean(), server_default=sa.false()),
        sa.Column("attempts", sa.Integer(), server_default="0"),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_jobs_status", "jobs", ["status", "queued_at"])
    op.create_index("idx_jobs_user", "jobs", ["user_id", "queued_at"])

    op.create_table(
        "usage_counters",
        sa.Column("subject", sa.Text(), primary_key=True),
        sa.Column("window_date", sa.Date(), primary_key=True),
        sa.Column("downloads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("separations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gpu_seconds", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_table("jobs")
    op.drop_index("idx_voice_models_active", table_name="voice_models")
    op.drop_table("voice_models")
    op.drop_index("idx_media_ytid", table_name="media")
    op.drop_index("idx_media_user", table_name="media")
    op.drop_index("idx_media_expires", table_name="media")
    op.drop_index("idx_media_hash", table_name="media")
    op.drop_table("media")
    op.drop_table("users")
