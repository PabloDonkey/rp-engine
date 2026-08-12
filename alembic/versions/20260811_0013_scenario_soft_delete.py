# ruff: noqa: I001

"""Add the scenario retirement stamp.

One nullable timestamp on `scenario_definitions` (S030). `deleted_at IS NULL` means the
scenario is still listed and still startable. A retired scenario keeps its row, keeps
resolving by id, and keeps every story that is already running it alive.

Existing rows stay null, which means "active" — the state every scenario was in before
this column existed.

Revision ID: 20260811_0013
Revises: 20260810_0012
Create Date: 2026-08-11 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260811_0013"
down_revision: str | Sequence[str] | None = "20260810_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scenario_definitions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scenario_definitions", "deleted_at")
