# ruff: noqa: I001

"""Add character definitions table.

Revision ID: 20260715_0002
Revises: 20260715_0001
Create Date: 2026-07-15 00:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260715_0002"
down_revision: str | Sequence[str] | None = "20260715_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_characters_name", table_name="characters")
    op.drop_index("ix_characters_owner_id", table_name="characters")
    op.drop_index("ix_characters_character_id", table_name="characters")
    op.drop_table("characters")
