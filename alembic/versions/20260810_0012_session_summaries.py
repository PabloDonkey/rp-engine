# ruff: noqa: I001

"""Add `session_summaries`, the table behind memory layer 01 (ADR-026, S023).

One row per session: the running "story so far" and the watermark that says how far it
reaches. `covers_through_turn` is the load-bearing column — it is what the background
worker re-reads to answer "is this session's recap behind?", which is what lets a job carry
a session id instead of a list of messages.

The foreign key cascades from `scenario_sessions`, so deleting a session takes its recap
with it. A recap without its transcript would be a claim about a story nobody can check.

Reversible with no data loss beyond the table itself: nothing outside it points at a recap,
and a dropped recap is rebuilt by the next turn's background pass.

Revision ID: 20260810_0012
Revises: 20260802_0011
Create Date: 2026-08-10 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260810_0012"
down_revision: str | Sequence[str] | None = "20260802_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_summaries",
        sa.Column(
            "session_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenario_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("covers_through_turn", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("session_summaries")
