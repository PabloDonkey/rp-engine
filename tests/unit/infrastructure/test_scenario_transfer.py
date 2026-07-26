import json
from pathlib import Path

from rp_engine.infrastructure.scenario_transfer import SYSTEM_OWNER_ID, read_scenario_directory


def test_reads_bundled_catalog() -> None:
    scenarios = read_scenario_directory("data/catalog")

    assert {s.id for s in scenarios} >= {"sealed-vault", "haunted-manor"}
    assert all(s.owner_id == SYSTEM_OWNER_ID for s in scenarios)


def test_missing_directory_is_empty(tmp_path: Path) -> None:
    assert read_scenario_directory(tmp_path / "nope") == []


def test_invalid_files_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "wrong-type.json").write_text("[]", encoding="utf-8")
    (tmp_path / "incomplete.json").write_text(json.dumps({"id": "x"}), encoding="utf-8")
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

    scenarios = read_scenario_directory(tmp_path)

    assert [s.id for s in scenarios] == ["good"]
