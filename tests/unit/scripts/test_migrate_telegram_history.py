import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast


def _load_migration_function() -> Callable[[Path | str], Any]:
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "migrate_telegram_history.py"
    spec = importlib.util.spec_from_file_location("migrate_telegram_history", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load migration script module")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Callable[[Path | str], Any], module.migrate_telegram_history)


def test_migration_moves_telegram_history_and_creates_backup(tmp_path: Path) -> None:
    migrate_telegram_history = _load_migration_function()
    data_dir = tmp_path / "data"
    memory_dir = data_dir / "memory"
    memory_dir.mkdir(parents=True)

    source_file = memory_dir / "user_123456789.json"
    source_payload = {
        "messages": [
            {
                "role": "user",
                "content": "hello",
            }
        ]
    }
    source_file.write_text(json.dumps(source_payload), encoding="utf-8")

    report = migrate_telegram_history(data_dir)

    assert report.migrated_files == 1
    assert report.backup_dir.exists()
    backup_file = report.backup_dir / "user_123456789.json"
    assert backup_file.exists()
    assert source_file.exists() is False

    migrated_files = list(memory_dir.glob("user_*.json"))
    assert len(migrated_files) == 1
    assert migrated_files[0].name != "user_123456789.json"

    user_id = migrated_files[0].stem.removeprefix("user_")
    profile_path = data_dir / "users" / user_id / "profile.json"
    identities_path = data_dir / "users" / user_id / "identities.json"
    index_path = data_dir / "adapters" / "telegram" / "identity_index.json"

    assert profile_path.exists()
    assert identities_path.exists()
    assert index_path.exists()

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["id"] == user_id

    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["123456789"] == user_id
