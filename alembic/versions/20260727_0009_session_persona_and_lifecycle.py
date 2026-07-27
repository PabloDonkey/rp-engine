# ruff: noqa: I001

"""Add the user persona and session lifecycle columns.

Two related additions to `scenario_sessions` (S015 + S016):

* **User persona** — `user_persona_name` / `user_persona_description`, the player's own
  character. Existing rows stay null, which means "no persona": `{{user}}` keeps
  resolving to the transport display name and no `[User Persona]` prompt section renders.
* **Lifecycle** — `updated_at` (backfilled from `created_at`, so a migration never
  falsifies history by claiming every old session was touched today) and a nullable
  `deleted_at`. `deleted_at IS NULL` becomes the definition of "the live session", so
  `ix_scenario_sessions_owner_definition` is reworked as a partial index over exactly
  those rows.

Revision ID: 20260727_0009
Revises: 20260726_0008
Create Date: 2026-07-27 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260727_0009"
down_revision: str | Sequence[str] | None = "20260726_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_scenario_sessions_owner_definition"
_INDEX_COLUMNS = ["owner_kind", "owner_id", "scenario_definition_id"]


def upgrade() -> None:
    op.add_column(
        "scenario_sessions",
        sa.Column("user_persona_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "scenario_sessions",
        sa.Column("user_persona_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "scenario_sessions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Added nullable, backfilled from the row's own creation time, then tightened — an
    # unconditional NOT NULL default would stamp every historical session with "now".
    op.add_column(
        "scenario_sessions",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE scenario_sessions SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("scenario_sessions", "updated_at", nullable=False)

    op.drop_index(_INDEX, table_name="scenario_sessions")
    op.create_index(
        _INDEX,
        "scenario_sessions",
        _INDEX_COLUMNS,
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="scenario_sessions")
    op.create_index(_INDEX, "scenario_sessions", _INDEX_COLUMNS, unique=False)

    op.drop_column("scenario_sessions", "updated_at")
    op.drop_column("scenario_sessions", "deleted_at")
    op.drop_column("scenario_sessions", "user_persona_description")
    op.drop_column("scenario_sessions", "user_persona_name")
