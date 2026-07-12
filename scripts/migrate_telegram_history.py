import asyncio
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from rp_engine.core.services.identity_resolver import IdentityResolver
from rp_engine.infrastructure.storage.json_user_identity_store import JsonUserIdentityStore


@dataclass(frozen=True, slots=True)
class MigrationReport:
    backup_dir: Path
    migrated_files: int
    skipped_files: int


def migrate_telegram_history(data_dir: Path | str = "data") -> MigrationReport:
    return asyncio.run(_migrate_telegram_history_async(Path(data_dir)))


async def _migrate_telegram_history_async(data_dir: Path) -> MigrationReport:
    memory_dir = data_dir / "memory"
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    backup_dir = data_dir / "backup" / f"telegram_history_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    if not memory_dir.exists():
        return MigrationReport(backup_dir=backup_dir, migrated_files=0, skipped_files=0)

    store = JsonUserIdentityStore(base_path=data_dir)
    resolver = IdentityResolver(store=store)

    migrated_files = 0
    skipped_files = 0
    for source_file in sorted(memory_dir.glob("user_*.json")):
        external_id = source_file.stem.removeprefix("user_")
        if _is_uuid(external_id) or not external_id.isdigit():
            skipped_files += 1
            continue

        shutil.copy2(source_file, backup_dir / source_file.name)
        user = await resolver.resolve_identity(
            provider="telegram",
            external_id=external_id,
            display_name=f"Telegram User {external_id}",
            metadata={},
        )
        target_file = memory_dir / f"user_{user.id}.json"
        shutil.move(str(source_file), str(target_file))
        migrated_files += 1

    return MigrationReport(
        backup_dir=backup_dir,
        migrated_files=migrated_files,
        skipped_files=skipped_files,
    )


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    report = migrate_telegram_history()
    print(
        f"Migration complete. Migrated={report.migrated_files} "
        f"Skipped={report.skipped_files} Backup={report.backup_dir}"
    )
