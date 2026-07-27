# ruff: noqa: I001

"""Add the session directives column.

A scenario session gains `directives`: the player's language preference, their
persistent scenario rules, and the pending one-turn director instruction. Existing rows
default to an empty object, which deserializes to the neutral defaults (language `auto`,
no rules, no director instruction), preserving current behavior.

Revision ID: 20260726_0008
Revises: 20260723_0007
Create Date: 2026-07-26 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260726_0008"
down_revision: str | Sequence[str] | None = "20260723_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scenario_sessions",
        sa.Column(
            "directives",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("scenario_sessions", "directives")
