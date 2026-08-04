"""Checks on the ADR files in `docs/adr/`.

The front matter is only worth writing if something reads it back. These tests are that
reader: they keep the file names, the status vocabulary, and — the point of the whole
exercise — both directions of every supersession link honest.

The front matter is parsed by hand rather than with PyYAML, which is not a declared
dependency of this project. The contract is six scalar or flat-list lines, so a real YAML
parser buys nothing here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

ADR_DIR = Path(__file__).resolve().parents[3] / "docs" / "adr"

FILE_NAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
ADR_ID = re.compile(r"^ADR-\d{3}$")
SCALAR = re.compile(r"^(\w+): (.*)$")

VALID_STATUSES = frozenset({"proposed", "accepted", "superseded", "rejected"})
REQUIRED_KEYS = ("id", "title", "status", "created", "supersedes", "superseded_by")


@dataclass(frozen=True)
class Adr:
    path: Path
    id: str
    title: str
    status: str
    created: str
    supersedes: tuple[str, ...]
    superseded_by: tuple[str, ...]
    body: str


def _parse_list(raw: str) -> tuple[str, ...]:
    inner = raw.strip()
    if not (inner.startswith("[") and inner.endswith("]")):
        raise AssertionError(f"expected a flat [ADR-001, ADR-002] list, got {raw!r}")
    items = [item.strip() for item in inner[1:-1].split(",") if item.strip()]
    return tuple(items)


def _load(path: Path) -> Adr:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path.name}: no YAML front matter")
    front, _, body = text[4:].partition("\n---\n")

    fields: dict[str, str] = {}
    for line in front.splitlines():
        match = SCALAR.match(line)
        if not match:
            raise AssertionError(f"{path.name}: cannot parse front matter line {line!r}")
        fields[match.group(1)] = match.group(2).strip()

    missing = [key for key in REQUIRED_KEYS if key not in fields]
    if missing:
        raise AssertionError(f"{path.name}: front matter is missing {missing}")

    return Adr(
        path=path,
        id=fields["id"],
        title=fields["title"].strip('"'),
        status=fields["status"],
        created=fields["created"],
        supersedes=_parse_list(fields["supersedes"]),
        superseded_by=_parse_list(fields["superseded_by"]),
        body=body,
    )


def _adr_files() -> list[Path]:
    return sorted(p for p in ADR_DIR.glob("*.md") if p.name[0].isdigit())


ADRS = [_load(path) for path in _adr_files()]
BY_ID = {adr.id: adr for adr in ADRS}


def test_adr_directory_is_not_empty() -> None:
    assert ADRS, f"no ADR files found in {ADR_DIR}"


@pytest.mark.parametrize("adr", ADRS, ids=lambda adr: adr.path.name)
def test_file_name_matches_the_convention_and_the_id(adr: Adr) -> None:
    match = FILE_NAME.match(adr.path.name)
    assert match, f"{adr.path.name}: expected NNNN-kebab-title.md"
    assert ADR_ID.match(adr.id), f"{adr.path.name}: id {adr.id!r} is not ADR-NNN"
    assert int(match.group(1)) == int(adr.id.removeprefix("ADR-")), (
        f"{adr.path.name}: file number does not match front matter id {adr.id}"
    )


@pytest.mark.parametrize("adr", ADRS, ids=lambda adr: adr.path.name)
def test_status_and_date_are_well_formed(adr: Adr) -> None:
    assert adr.status in VALID_STATUSES, f"{adr.path.name}: unknown status {adr.status!r}"
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", adr.created), (
        f"{adr.path.name}: created {adr.created!r} is not YYYY-MM-DD"
    )


@pytest.mark.parametrize("adr", ADRS, ids=lambda adr: adr.path.name)
def test_body_starts_with_the_matching_heading(adr: Adr) -> None:
    heading = adr.body.strip().splitlines()[0]
    assert heading == f"# {adr.id} — {adr.title}", (
        f"{adr.path.name}: heading {heading!r} does not match the front matter"
    )


@pytest.mark.parametrize("adr", ADRS, ids=lambda adr: adr.path.name)
def test_status_is_not_repeated_in_the_body(adr: Adr) -> None:
    """Front matter is the single source of truth for status and date."""
    assert not re.search(r"^\*\*(Status|Date):\*\*", adr.body, re.M), (
        f"{adr.path.name}: body repeats Status/Date — they belong in the front matter only"
    )


@pytest.mark.parametrize("adr", ADRS, ids=lambda adr: adr.path.name)
def test_supersession_links_resolve_and_mirror(adr: Adr) -> None:
    for other_id in adr.supersedes:
        other = BY_ID.get(other_id)
        assert other is not None, f"{adr.path.name}: supersedes unknown {other_id}"
        assert adr.id in other.superseded_by, (
            f"{adr.path.name} supersedes {other_id}, but {other.path.name} does not list "
            f"{adr.id} in superseded_by"
        )
    for other_id in adr.superseded_by:
        other = BY_ID.get(other_id)
        assert other is not None, f"{adr.path.name}: superseded_by unknown {other_id}"
        assert adr.id in other.supersedes, (
            f"{adr.path.name} is superseded_by {other_id}, but {other.path.name} does not "
            f"list {adr.id} in supersedes"
        )


@pytest.mark.parametrize("adr", ADRS, ids=lambda adr: adr.path.name)
def test_superseding_adr_explains_the_scope(adr: Adr) -> None:
    """A list of ids does not tell a reader which parts of the old decision died."""
    if adr.supersedes:
        assert re.search(r"^## Supersedes\s*$", adr.body, re.M), (
            f"{adr.path.name}: supersedes {list(adr.supersedes)} but has no "
            f"'## Supersedes' section explaining the scope"
        )


def test_index_lists_every_adr() -> None:
    index = (ADR_DIR / "README.md").read_text(encoding="utf-8")
    for adr in ADRS:
        assert f"({adr.path.name})" in index, f"{adr.path.name} is missing from the index table"
