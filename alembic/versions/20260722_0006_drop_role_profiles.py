# ruff: noqa: I001

"""Drop the scenario role_profiles column.

RoleProfile was an abstract-role concept that never drove any runtime behavior: roles
are cast directly to concrete characters via a scenario session's active_participants.
The column and its domain type are removed. Should casting be reintroduced later, it can
come back as a fresh migration.

Revision ID: 20260722_0006
Revises: 20260722_0005
Create Date: 2026-07-22 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260722_0006"
down_revision: str | Sequence[str] | None = "20260722_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("scenario_definitions", "role_profiles")


def downgrade() -> None:
    op.add_column(
        "scenario_definitions",
        sa.Column(
            "role_profiles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
