# ruff: noqa: I001

"""Add `lorebook_entries`, the table behind memory layer 02 (ADR-026, S024).

Authored lore, scoped to a scenario definition, matched against the recent turn's text
with Postgres full-text search rather than being carried in every prompt. The composite
primary key `(scenario_definition_id, id)` mirrors how entries are addressed everywhere
else in the code: always by scenario first.

`trigger_query_expr` is plain text, not a `tsquery`-typed column — it is cast to
`tsquery` only inside the matching query (see `PostgresLorebookStore`), which avoids
needing a SQLAlchemy `TSQUERY` type. No index on it: a scenario's lorebook is a handful
of rows by design, so a full scan costs nothing.

The foreign key cascades from `scenario_definitions`, so retiring a scenario's row (soft
delete, see ADR migration 0013) does not touch this table, but hard-deleting the
definition takes its lore with it.

Reversible with no data loss beyond the table itself: nothing outside it points at a
lore entry.

Revision ID: 20260903_0014
Revises: 20260811_0013
Create Date: 2026-09-03 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260903_0014"
down_revision: str | Sequence[str] | None = "20260811_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lorebook_entries",
        sa.Column(
            "scenario_definition_id",
            sa.String(length=128),
            sa.ForeignKey("scenario_definitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "trigger_keys",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("trigger_query_expr", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column(
            "related_entry_ids",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lorebook_entries")
