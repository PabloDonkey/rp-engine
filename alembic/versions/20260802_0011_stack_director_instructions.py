# ruff: noqa: I001

"""Convert the single `director_instruction` string into a `director_instructions` list.

S020 turns the one-turn director note into a **stack** — `/director` appends instead of
silently replacing — which changes the shape of one key inside the `scenario_sessions
.directives` JSONB blob written by `20260726_0008`:

```
{"director_instruction": "raise the stakes"}   →  {"director_instructions": ["raise the stakes"]}
{"director_instruction": ""}                   →  {"director_instructions": []}
```

No DDL: JSONB needs no column change. What it does need is the **data** converted, because a
row left in the old shape reads back as an empty queue — the player's armed note would vanish
on the next load, silently, which is the same class of "the code was fixed and the data was
not" failure `20260727_0010` had to clean up after.

Both directions are exact for every row this engine can have written: at most one note existed
before the upgrade, so `downgrade` only ever collapses a single-element list. A queue built
*after* the upgrade would not fit the old single-string slot, so the downgrade keeps the first
note (the earliest one the player sent) rather than inventing a joined string the prompt
builder never rendered.

Revision ID: 20260802_0011
Revises: 20260727_0010
Create Date: 2026-08-02 00:00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260802_0011"
down_revision: str | Sequence[str] | None = "20260727_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# `-` drops the old key; a non-empty note becomes a one-element array, an empty or absent
# one becomes `[]`. Rows already carrying `director_instructions` are left alone so the
# migration is safe to re-run over a partially converted table.
_UPGRADE = """
UPDATE scenario_sessions
SET directives =
    (directives - 'director_instruction')
    || jsonb_build_object(
        'director_instructions',
        CASE
            WHEN COALESCE(TRIM(directives ->> 'director_instruction'), '') = ''
                THEN '[]'::jsonb
            ELSE jsonb_build_array(TRIM(directives ->> 'director_instruction'))
        END
    )
WHERE directives ? 'director_instruction'
"""

_DOWNGRADE = """
UPDATE scenario_sessions
SET directives =
    (directives - 'director_instructions')
    || jsonb_build_object(
        'director_instruction',
        COALESCE(directives -> 'director_instructions' ->> 0, '')
    )
WHERE directives ? 'director_instructions'
"""


def upgrade() -> None:
    op.execute(_UPGRADE)


def downgrade() -> None:
    op.execute(_DOWNGRADE)
