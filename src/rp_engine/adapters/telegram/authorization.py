import json
from pathlib import Path


class TelegramAuthorization:
    def __init__(
        self,
        allowed_user_ids: set[str],
        allowed_group_ids: set[str] | None = None,
        directory: Path | None = None,
        admin_user_id: str = "",
    ) -> None:
        self._allowed_user_ids = allowed_user_ids
        self._allowed_group_ids = allowed_group_ids or set()
        self._directory = directory
        self._admin_user_id = str(admin_user_id) if admin_user_id else ""

    @classmethod
    def from_directory(
        cls, directory: str | Path, admin_user_id: str = ""
    ) -> "TelegramAuthorization":
        directory_path = Path(directory)
        users = cls._load_ids(directory_path / "users.json", "allowed_user_ids")
        groups = cls._load_ids(directory_path / "groups.json", "allowed_group_ids")
        return cls(
            allowed_user_ids=users,
            allowed_group_ids=groups,
            directory=directory_path,
            admin_user_id=admin_user_id,
        )

    def is_authorized(self, user_id: str) -> bool:
        # Fail closed: an empty allowlist denies everyone. The configured admin is always
        # allowed so a missing/emptied users.json can never lock the operator out.
        if self._admin_user_id and str(user_id) == self._admin_user_id:
            return True
        if not self._allowed_user_ids:
            return False
        return str(user_id) in self._allowed_user_ids

    def is_private_chat_authorized(self, user_id: str) -> bool:
        return self.is_authorized(user_id)

    def has_explicit_private_user(self, user_id: str) -> bool:
        return str(user_id) in self._allowed_user_ids

    def is_group_chat_authorized(self, group_id: str) -> bool:
        if not self._allowed_group_ids:
            return True
        return group_id in self._allowed_group_ids

    def add_private_user(self, user_id: str) -> bool:
        normalized_user_id = str(user_id)
        if normalized_user_id in self._allowed_user_ids:
            return False
        self._allowed_user_ids.add(normalized_user_id)
        return True

    def remove_private_user(self, user_id: str) -> bool:
        normalized_user_id = str(user_id)
        if normalized_user_id not in self._allowed_user_ids:
            return False
        self._allowed_user_ids.discard(normalized_user_id)
        return True

    def allowed_user_ids(self) -> frozenset[str]:
        return frozenset(self._allowed_user_ids)

    def persist(self) -> None:
        if self._directory is None:
            return

        self._directory.mkdir(parents=True, exist_ok=True)
        users_path = self._directory / "users.json"
        users_payload = {"allowed_user_ids": sorted(self._allowed_user_ids)}
        with users_path.open("w", encoding="utf-8") as file:
            json.dump(users_payload, file, ensure_ascii=True, indent=2)

    @staticmethod
    def _load_ids(file_path: Path, expected_key: str) -> set[str]:
        if not file_path.exists():
            return set()

        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        if isinstance(payload, list):
            return {str(value) for value in payload}

        if not isinstance(payload, dict):
            return set()

        values = payload.get(expected_key)
        if isinstance(values, list):
            return {str(value) for value in values}

        generic_values = payload.get("ids")
        if isinstance(generic_values, list):
            return {str(value) for value in generic_values}

        return set()
