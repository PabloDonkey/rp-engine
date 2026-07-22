import json
from pathlib import Path

from rp_engine.infrastructure.catalog.scenario_catalog import SYSTEM_OWNER_ID, ScenarioCatalog


def test_loads_bundled_catalog() -> None:
    catalog = ScenarioCatalog.from_directory("data/catalog")

    scenarios = catalog.list()
    assert {s.id for s in scenarios} >= {"sealed-vault", "haunted-manor"}
    # Listing is sorted by name.
    names = [s.name for s in scenarios]
    assert names == sorted(names, key=str.lower)


def test_get_returns_scenario_and_none() -> None:
    catalog = ScenarioCatalog.from_directory("data/catalog")

    scenario = catalog.get("sealed-vault")
    assert scenario is not None
    assert scenario.owner_id == SYSTEM_OWNER_ID
    assert scenario.initial_context
    assert catalog.get("does-not-exist") is None


def test_missing_directory_is_empty(tmp_path: Path) -> None:
    catalog = ScenarioCatalog.from_directory(tmp_path / "nope")
    assert catalog.is_empty()
    assert catalog.list() == []


def test_invalid_files_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "wrong-type.json").write_text("[]", encoding="utf-8")
    (tmp_path / "incomplete.json").write_text(
        json.dumps({"id": "x"}), encoding="utf-8"
    )
    (tmp_path / "good.json").write_text(
        json.dumps(
            {
                "id": "good",
                "owner_id": str(SYSTEM_OWNER_ID),
                "name": "Good",
                "description": "",
            }
        ),
        encoding="utf-8",
    )

    catalog = ScenarioCatalog.from_directory(tmp_path)

    assert [s.id for s in catalog.list()] == ["good"]
