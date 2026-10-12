"""users: sign up with a username instead of an email

Existing rows keep their value (older accounts simply use their email as the id).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "email", new_column_name="username")


def downgrade() -> None:
    op.alter_column("users", "username", new_column_name="email")
