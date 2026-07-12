import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from rp_engine.core.user.identity import UserIdentity
from rp_engine.core.user.user import User


class JsonUserIdentityStore:
    def __init__(self, base_path: Path | str = "data") -> None:
        self._base_path = Path(base_path)
        self._users_path = self._base_path / "users"
        self._adapters_path = self._base_path / "adapters"
        self._lock = asyncio.Lock()

    async def get_user_by_identity(self, *, provider: str, external_id: str) -> User | None:
        index_path = self._identity_index_path(provider)
        if not index_path.exists():
            return None

        index_payload = await asyncio.to_thread(self._read_payload, index_path)
        user_id = index_payload.get(external_id)
        if not isinstance(user_id, str):
            return None

        return await self._load_user_by_id(user_id)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self._load_user_by_id(str(user_id))

    async def create_user_with_identity(
        self,
        *,
        display_name: str,
        identity: UserIdentity,
    ) -> User:
        async with self._lock:
            existing = await self.get_user_by_identity(
                provider=identity.provider,
                external_id=identity.external_id,
            )
            if existing is not None:
                return existing

            user = User.create(display_name=display_name, identities=(identity,))
            await self._persist_user(user)
            await self._update_identity_index(identity=identity, user_id=str(user.id))
            return user

    async def _load_user_by_id(self, user_id: str) -> User | None:
        user_path = self._users_path / user_id
        profile_path = user_path / "profile.json"
        identities_path = user_path / "identities.json"
        if not profile_path.exists() or not identities_path.exists():
            return None

        profile_payload = await asyncio.to_thread(self._read_payload, profile_path)
        identities_payload = await asyncio.to_thread(self._read_payload, identities_path)

        stored_id = profile_payload.get("id")
        display_name = profile_payload.get("display_name")
        if not isinstance(stored_id, str) or not isinstance(display_name, str):
            return None

        identities_map = identities_payload.get("identities")
        identities: list[UserIdentity] = []
        if isinstance(identities_map, dict):
            for provider, raw in identities_map.items():
                if not isinstance(provider, str) or not isinstance(raw, dict):
                    continue
                external_id = raw.get("external_id")
                metadata = raw.get("metadata", {})
                if not isinstance(external_id, str) or not isinstance(metadata, dict):
                    continue
                normalized_metadata = {
                    key: value
                    for key, value in metadata.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
                identities.append(
                    UserIdentity(
                        provider=provider,
                        external_id=external_id,
                        metadata=normalized_metadata,
                    )
                )

        return User(
            id=UUID(stored_id),
            display_name=display_name,
            identities=tuple(identities),
        )

    async def _persist_user(self, user: User) -> None:
        user_path = self._users_path / str(user.id)
        user_path.mkdir(parents=True, exist_ok=True)

        profile_payload = {
            "id": str(user.id),
            "display_name": user.display_name,
        }
        identities_payload = {
            "identities": {
                identity.provider: {
                    "external_id": identity.external_id,
                    "metadata": identity.metadata,
                }
                for identity in user.identities
            }
        }

        await asyncio.to_thread(self._write_payload, user_path / "profile.json", profile_payload)
        await asyncio.to_thread(
            self._write_payload,
            user_path / "identities.json",
            identities_payload,
        )

    async def _update_identity_index(self, *, identity: UserIdentity, user_id: str) -> None:
        index_path = self._identity_index_path(identity.provider)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        current = await asyncio.to_thread(self._read_payload, index_path)
        current[identity.external_id] = user_id
        await asyncio.to_thread(self._write_payload, index_path, current)

    def _identity_index_path(self, provider: str) -> Path:
        return self._adapters_path / provider / "identity_index.json"

    @staticmethod
    def _read_payload(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            return loaded
        return {}

    @staticmethod
    def _write_payload(path: Path, payload: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=True, indent=2)
