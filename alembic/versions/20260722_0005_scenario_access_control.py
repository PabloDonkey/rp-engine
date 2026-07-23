# ruff: noqa: I001

"""Add scenario access-control columns.

Scenarios gain a `visibility` (PUBLIC / UNLISTED / RESTRICTED) and an
`allowed_group_chat_ids` allow-list of Telegram chat ids used to hide a scenario or
lock it to specific groups. Existing rows default to PUBLIC with an empty allow-list,
preserving current behavior.

Revision ID: 20260722_0005
Revises: 20260722_0004
Create Date: 2026-07-22 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260722_0005"
down_revision: str | Sequence[str] | None = "20260722_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scenario_definitions",
        sa.Column(
            "visibility",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'PUBLIC'"),
        ),
    )
    op.add_column(
        "scenario_definitions",
        sa.Column(
            "allowed_group_chat_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("scenario_definitions", "allowed_group_chat_ids")
    op.drop_column("scenario_definitions", "visibility")
