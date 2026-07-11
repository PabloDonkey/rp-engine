import json
from pathlib import Path


class TelegramAuthorization:
    def __init__(
        self,
        allowed_user_ids: set[str],
        allowed_group_ids: set[str] | None = None,
    ) -> None:
        self._allowed_user_ids = allowed_user_ids
        self._allowed_group_ids = allowed_group_ids or set()

    @classmethod
    def from_directory(cls, directory: str | Path) -> "TelegramAuthorization":
        directory_path = Path(directory)
        users = cls._load_ids(directory_path / "users.json", "allowed_user_ids")
        groups = cls._load_ids(directory_path / "groups.json", "allowed_group_ids")
        return cls(allowed_user_ids=users, allowed_group_ids=groups)

    def is_authorized(self, user_id: str) -> bool:
        if not self._allowed_user_ids:
            return True
        return user_id in self._allowed_user_ids

    def is_private_chat_authorized(self, user_id: str) -> bool:
        return self.is_authorized(user_id)

    def is_group_chat_authorized(self, group_id: str) -> bool:
        if not self._allowed_group_ids:
            return True
        return group_id in self._allowed_group_ids

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
