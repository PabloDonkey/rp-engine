# ruff: noqa: I001

"""Postgres foundation for session and conversation stores.

Revision ID: 20260715_0001
Revises:
Create Date: 2026-07-15 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260715_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_kind", sa.String(length=16), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", sa.String(length=128), nullable=False),
        sa.Column("world_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sessions_owner_relationship",
        "sessions",
        ["owner_kind", "owner_id", "character_id", "world_id"],
        unique=False,
    )

    op.create_table(
        "active_sessions",
        sa.Column("owner_kind", sa.String(length=16), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("owner_kind", "owner_id"),
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_key", sa.String(length=255), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_messages_memory_key",
        "conversation_messages",
        ["memory_key"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_messages_session_id",
        "conversation_messages",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_messages_memory_order",
        "conversation_messages",
        ["memory_key", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_memory_order", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_session_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_memory_key", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_table("active_sessions")
    op.drop_index("ix_sessions_owner_relationship", table_name="sessions")
    op.drop_table("sessions")
