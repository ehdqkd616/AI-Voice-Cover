"""users: 승인 상태(pending/approved/rejected/suspended)·이름·가입 메모 + 감사 로그

is_approved(bool) → status. 기존 승인 회원은 approved, 미승인 회원은 pending.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-12

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(50), nullable=False, server_default=""))
    op.add_column("users", sa.Column("signup_note", sa.Text()))
    op.add_column("users", sa.Column("status", sa.String(20), nullable=False, server_default="pending"))
    op.add_column("users", sa.Column("reject_reason", sa.Text()))
    op.add_column("users", sa.Column("approved_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE users SET status = CASE WHEN is_approved THEN 'approved' ELSE 'pending' END, "
               "approved_at = CASE WHEN is_approved THEN created_at END")
    op.drop_column("users", "is_approved")
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(64)),
        sa.Column("detail", postgresql.JSONB()),
        sa.Column("ip", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.add_column("users", sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE users SET is_approved = (status = 'approved')")
    op.drop_index("ix_users_status", table_name="users")
    for col in ("last_login_at", "approved_at", "reject_reason", "status", "signup_note", "name"):
        op.drop_column("users", col)
