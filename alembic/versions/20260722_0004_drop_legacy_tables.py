# ruff: noqa: I001

"""Drop legacy character-centric tables.

The scenario-centric architecture supersedes the character-centric runtime. The
`sessions`, `active_sessions`, and `characters` tables are no longer used by any store
(runtime state lives in `scenario_sessions` / `active_scenario_sessions`, and scenario
characters are embedded in `scenario_definitions`). This migration drops them.

Revision ID: 20260722_0004
Revises: 20260721_0003
Create Date: 2026-07-22 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260722_0004"
down_revision: str | Sequence[str] | None = "20260721_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("active_sessions")
    op.drop_index("ix_sessions_owner_relationship", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_characters_name", table_name="characters")
    op.drop_index("ix_characters_owner_id", table_name="characters")
    op.drop_index("ix_characters_character_id", table_name="characters")
    op.drop_table("characters")


def downgrade() -> None:
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
        "characters",
        sa.Column("pk", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", sa.String(length=128), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("greeting", sa.Text(), nullable=False, server_default=sa.text("''")),
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("character_id", name="uq_characters_character_id"),
    )
    op.create_index("ix_characters_character_id", "characters", ["character_id"], unique=False)
    op.create_index("ix_characters_owner_id", "characters", ["owner_id"], unique=False)
    op.create_index("ix_characters_name", "characters", ["name"], unique=False)
