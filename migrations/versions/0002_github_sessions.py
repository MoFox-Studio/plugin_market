"""Add GitHub OAuth browser sessions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_github_sessions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply GitHub session tables."""

    op.create_table(
        "auth_sessions",
        sa.Column("session_id", sa.String(length=160), primary_key=True),
        sa.Column("author_id", sa.String(length=120), sa.ForeignKey("authors.author_id"), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_sessions_author_id", "auth_sessions", ["author_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(length=160), primary_key=True),
        sa.Column("redirect_to", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])


def downgrade() -> None:
    """Drop GitHub session tables."""

    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_table("oauth_states")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_author_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
