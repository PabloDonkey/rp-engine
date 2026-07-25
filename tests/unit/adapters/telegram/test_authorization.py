import json
from pathlib import Path

from rp_engine.adapters.telegram.authorization import TelegramAuthorization


def test_authorization_denies_everyone_when_whitelist_is_empty() -> None:
    auth = TelegramAuthorization(allowed_user_ids=set())

    assert auth.is_private_chat_authorized("123") is False


def test_authorization_always_allows_admin_even_when_whitelist_is_empty() -> None:
    auth = TelegramAuthorization(allowed_user_ids=set(), admin_user_id="124105002")

    assert auth.is_private_chat_authorized("124105002") is True
    assert auth.is_private_chat_authorized("999") is False


def test_authorization_always_allows_admin_even_when_not_in_whitelist() -> None:
    auth = TelegramAuthorization(allowed_user_ids={"123"}, admin_user_id="124105002")

    assert auth.is_private_chat_authorized("124105002") is True


def test_authorization_denies_users_not_in_whitelist() -> None:
    auth = TelegramAuthorization(allowed_user_ids={"123"})

    assert auth.is_private_chat_authorized("999") is False
    assert auth.is_private_chat_authorized("123") is True


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

    assert auth.is_private_chat_authorized("124105002") is True
    assert auth.is_private_chat_authorized("7881079571") is True
    assert auth.is_private_chat_authorized("999") is False


def test_authorization_denies_all_when_users_file_missing(tmp_path: Path) -> None:
    auth_dir = tmp_path / "authorization"
    auth_dir.mkdir()

    auth = TelegramAuthorization.from_directory(auth_dir)

    assert auth.is_private_chat_authorized("any-user") is False


def test_authorization_from_directory_still_allows_admin_when_file_missing(tmp_path: Path) -> None:
    auth_dir = tmp_path / "authorization"
    auth_dir.mkdir()

    auth = TelegramAuthorization.from_directory(auth_dir, admin_user_id="124105002")

    assert auth.is_private_chat_authorized("124105002") is True
    assert auth.is_private_chat_authorized("any-user") is False


def test_remove_private_user_blocks_a_previously_allowed_user() -> None:
    auth = TelegramAuthorization(allowed_user_ids={"123"})

    assert auth.remove_private_user("123") is True
    assert auth.is_private_chat_authorized("123") is False


def test_remove_private_user_is_a_no_op_when_not_present() -> None:
    auth = TelegramAuthorization(allowed_user_ids={"123"})

    assert auth.remove_private_user("999") is False
    assert auth.is_private_chat_authorized("123") is True


def test_remove_private_user_does_not_block_the_admin() -> None:
    auth = TelegramAuthorization(allowed_user_ids={"124105002"}, admin_user_id="124105002")

    auth.remove_private_user("124105002")

    assert auth.is_private_chat_authorized("124105002") is True


def test_group_authorization_uses_group_whitelist() -> None:
    auth = TelegramAuthorization(
        allowed_user_ids=set(),
        allowed_group_ids={"-1001"},
    )

    assert auth.is_group_chat_authorized("-1001") is True
    assert auth.is_group_chat_authorized("-1002") is False


def test_group_authorization_allows_all_when_whitelist_is_empty() -> None:
    auth = TelegramAuthorization(
        allowed_user_ids={"123"},
        allowed_group_ids=set(),
    )

    assert auth.is_group_chat_authorized("-999") is True
