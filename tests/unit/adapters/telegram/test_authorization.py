import json
from pathlib import Path

from rp_engine.adapters.telegram.authorization import TelegramAuthorization


def test_authorization_allows_everyone_when_whitelist_is_empty() -> None:
    auth = TelegramAuthorization(allowed_user_ids=set())

    assert auth.is_authorized("123") is True


def test_authorization_denies_users_not_in_whitelist() -> None:
    auth = TelegramAuthorization(allowed_user_ids={"123"})

    assert auth.is_authorized("999") is False
    assert auth.is_authorized("123") is True


def test_authorization_loads_users_from_json_directory(tmp_path: Path) -> None:
    auth_dir = tmp_path / "authorization"
    auth_dir.mkdir()
    users_path = auth_dir / "users.json"
    groups_path = auth_dir / "groups.json"
    users_path.write_text(
        json.dumps({"allowed_user_ids": [124105002, 7881079571]}),
        encoding="utf-8",
    )
    groups_path.write_text(
        json.dumps({"allowed_group_ids": []}),
        encoding="utf-8",
    )

    auth = TelegramAuthorization.from_directory(auth_dir)

    assert auth.is_authorized("124105002") is True
    assert auth.is_authorized("7881079571") is True
    assert auth.is_authorized("999") is False


def test_authorization_defaults_to_allow_all_when_users_file_missing(tmp_path: Path) -> None:
    auth_dir = tmp_path / "authorization"
    auth_dir.mkdir()

    auth = TelegramAuthorization.from_directory(auth_dir)

    assert auth.is_authorized("any-user") is True
