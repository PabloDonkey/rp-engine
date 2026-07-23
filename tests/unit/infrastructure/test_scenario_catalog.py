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


def _write_scenario(directory: Path, scenario_id: str, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{scenario_id}.json").write_text(
        json.dumps(
            {
                "id": scenario_id,
                "owner_id": str(SYSTEM_OWNER_ID),
                "name": name,
                "description": "",
            }
        ),
        encoding="utf-8",
    )


def test_from_directories_merges_distinct_scenarios(tmp_path: Path) -> None:
    curated = tmp_path / "curated"
    local = tmp_path / "local"
    _write_scenario(curated, "sealed-vault", "Sealed Vault")
    _write_scenario(local, "haunted-manor", "Haunted Manor")

    catalog = ScenarioCatalog.from_directories([curated, local])

    assert {s.id for s in catalog.list()} == {"sealed-vault", "haunted-manor"}


def test_from_directories_later_directory_wins_on_id_collision(tmp_path: Path) -> None:
    curated = tmp_path / "curated"
    local = tmp_path / "local"
    _write_scenario(curated, "sealed-vault", "Curated Vault")
    _write_scenario(local, "sealed-vault", "Local Override Vault")

    catalog = ScenarioCatalog.from_directories([curated, local])

    scenario = catalog.get("sealed-vault")
    assert scenario is not None
    assert scenario.name == "Local Override Vault"
