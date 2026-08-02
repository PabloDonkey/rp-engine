# ruff: noqa: I001

"""Supersede the sessions orphaned before soft delete existed, and enforce one live session.

`20260727_0009` added `deleted_at` and left every existing row NULL — correct for the column
default, wrong for the data: **every session orphaned by a pre-S016 `/restart` was therefore
still "live"**. With several live rows per (owner, scenario), `find_by_definition` keeps
picking among them, so `/play <id>` can still resume a pre-restart story. That is the exact
bug S016 set out to kill, surviving in the data rather than in the code.

Two steps:

1. **Backfill.** For each (owner_kind, owner_id, scenario_definition_id) keep exactly one
   session live and stamp the rest. "The one really being played" is decided by, in order:
   the owner's active-session pointer, then the most recent conversation message, then
   creation time. `deleted_at` is set to that session's own last sign of life rather than
   `now()`, so the column never claims a session from July was superseded on migration day.

2. **Make it impossible again.** `ix_scenario_sessions_owner_definition` becomes a *unique*
   partial index. "One live session per owner per scenario" is the invariant the engine has
   always assumed; nothing in `PlaythroughService` can legitimately create a second one
   (`_begin` runs only when no live session exists, or after `_reset` has stamped the
   outgoing one). Making the database enforce it turns a silent, non-deterministic wrong
   answer into a loud failure.

Revision ID: 20260727_0010
Revises: 20260727_0009
Create Date: 2026-07-27 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260727_0010"
down_revision: str | Sequence[str] | None = "20260727_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_scenario_sessions_owner_definition"
_INDEX_COLUMNS = ["owner_kind", "owner_id", "scenario_definition_id"]

_BACKFILL = """
WITH ranked AS (
    SELECT
        s.id,
        COALESCE(last_message.at, s.updated_at) AS last_alive_at,
        ROW_NUMBER() OVER (
            PARTITION BY s.owner_kind, s.owner_id, s.scenario_definition_id
            ORDER BY
                (active.session_id IS NOT NULL) DESC,
                last_message.at DESC NULLS LAST,
                s.created_at DESC
        ) AS position
    FROM scenario_sessions s
    LEFT JOIN active_scenario_sessions active ON active.session_id = s.id
    LEFT JOIN LATERAL (
        SELECT MAX(m.created_at) AS at
        FROM conversation_messages m
        WHERE m.session_id = s.id
    ) last_message ON TRUE
    WHERE s.deleted_at IS NULL
)
UPDATE scenario_sessions target
SET deleted_at = ranked.last_alive_at
FROM ranked
WHERE target.id = ranked.id
  AND ranked.position > 1
"""


def upgrade() -> None:
    op.execute(_BACKFILL)

    op.drop_index(_INDEX, table_name="scenario_sessions")
    op.create_index(
        _INDEX,
        "scenario_sessions",
        _INDEX_COLUMNS,
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    # The index reverts; the backfill deliberately does not. Un-stamping would have to
    # un-stamp *every* superseded session, including ones a real `/restart` retired, which
    # would resurrect the bug this migration exists to fix. Losing the orphan/current
    # distinction is not worth restoring on the way down.
    op.drop_index(_INDEX, table_name="scenario_sessions")
    op.create_index(
        _INDEX,
        "scenario_sessions",
        _INDEX_COLUMNS,
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
