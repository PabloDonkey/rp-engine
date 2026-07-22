# ruff: noqa: I001

"""Add scenario definition and session tables.

Revision ID: 20260721_0003
Revises: 20260715_0002
Create Date: 2026-07-21 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260721_0003"
down_revision: str | Sequence[str] | None = "20260715_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _jsonb_object() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "scenario_definitions",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("world", _jsonb_object(), nullable=True),
        sa.Column(
            "role_profiles",
            _jsonb_object(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "characters",
            _jsonb_object(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "rules",
            _jsonb_object(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("story_graph", _jsonb_object(), nullable=True),
        sa.Column("initial_context", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "metadata",
            _jsonb_object(),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scenario_definitions_owner_id",
        "scenario_definitions",
        ["owner_id"],
        unique=False,
    )

    op.create_table(
        "scenario_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_definition_id", sa.String(length=128), nullable=False),
        sa.Column("owner_kind", sa.String(length=16), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "active_participants",
            _jsonb_object(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "world_state",
            _jsonb_object(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "story_progress",
            _jsonb_object(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata",
            _jsonb_object(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scenario_sessions_scenario_definition_id",
        "scenario_sessions",
        ["scenario_definition_id"],
        unique=False,
    )
    op.create_index(
        "ix_scenario_sessions_owner_definition",
        "scenario_sessions",
        ["owner_kind", "owner_id", "scenario_definition_id"],
        unique=False,
    )

    op.create_table(
        "active_scenario_sessions",
        sa.Column("owner_kind", sa.String(length=16), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["scenario_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("owner_kind", "owner_id"),
    )


def downgrade() -> None:
    op.drop_table("active_scenario_sessions")
    op.drop_index(
        "ix_scenario_sessions_owner_definition", table_name="scenario_sessions"
    )
    op.drop_index(
        "ix_scenario_sessions_scenario_definition_id", table_name="scenario_sessions"
    )
    op.drop_table("scenario_sessions")
    op.drop_index("ix_scenario_definitions_owner_id", table_name="scenario_definitions")
    op.drop_table("scenario_definitions")
