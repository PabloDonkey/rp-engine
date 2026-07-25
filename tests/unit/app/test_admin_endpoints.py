from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

from fastapi.testclient import TestClient

from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.app.main import create_app
from rp_engine.application.services.admin_service import AdminUserSummary
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.user.identity import UserIdentity
from rp_engine.core.user.user import User
from rp_engine.infrastructure.config.settings import Settings

USER_ID = UUID("00000000-0000-0000-0000-000000000042")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000999")


def _setup(tmp_path: Path) -> tuple[TestClient, Any]:
    settings = Settings(
        telegram_enabled=False,
        telegram_authorization_dir=str(tmp_path / "authorization"),
    )
    app = create_app(settings)
    return TestClient(app), app.state.container


def _telegram_user(*, display_name: str = "Pablo") -> User:
    return User(
        id=USER_ID,
        display_name=display_name,
        identities=(UserIdentity(provider="telegram", external_id="555", metadata={}),),
    )


def _session() -> ScenarioSession:
    return ScenarioSession(
        id=SESSION_ID, scenario_definition_id="def-1", owner_kind="user", owner_id=USER_ID
    )


def test_list_users_reports_blocked_status(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.list_users = AsyncMock(
        return_value=[AdminUserSummary(user=_telegram_user(), session_count=2)]
    )
    # container.telegram_authorization already has an empty allowlist (fresh tmp_path dir),
    # so "555" is unauthorized/blocked by default under fail-closed semantics.

    response = client.get("/admin/users")

    assert response.status_code == 200
    payload = cast(list[dict[str, Any]], response.json())
    assert payload == [
        {
            "id": str(USER_ID),
            "display_name": "Pablo",
            "telegram_external_id": "555",
            "session_count": 2,
            "is_blocked": True,
        }
    ]


def test_list_user_sessions_404_for_unknown_user(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_user = AsyncMock(return_value=None)

    response = client.get(f"/admin/users/{USER_ID}/sessions")

    assert response.status_code == 404


def test_list_user_sessions_returns_sessions(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_user = AsyncMock(return_value=_telegram_user())
    container.admin_service.list_user_sessions = AsyncMock(return_value=[_session()])

    response = client.get(f"/admin/users/{USER_ID}/sessions")

    assert response.status_code == 200
    payload = cast(list[dict[str, Any]], response.json())
    assert payload[0]["id"] == str(SESSION_ID)


def test_get_session_404_when_missing(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=None)

    response = client.get(f"/admin/sessions/{SESSION_ID}")

    assert response.status_code == 404


def test_get_session_includes_message_count(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=_session())
    container.admin_service.get_session_transcript = AsyncMock(
        return_value=[ConversationMessage(role=ConversationRole.USER, content="hi")]
    )

    response = client.get(f"/admin/sessions/{SESSION_ID}")

    assert response.status_code == 200
    assert response.json()["message_count"] == 1


def test_get_session_transcript(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=_session())
    container.admin_service.get_session_transcript = AsyncMock(
        return_value=[ConversationMessage(role=ConversationRole.USER, content="hi")]
    )

    response = client.get(f"/admin/sessions/{SESSION_ID}/transcript")

    assert response.status_code == 200
    assert response.json() == [{"role": "user", "content": "hi", "metadata": {}}]


def test_get_session_traces(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=_session())
    container.admin_service.get_session_traces = AsyncMock(return_value=[{"turn": 1}])

    response = client.get(f"/admin/sessions/{SESSION_ID}/traces")

    assert response.status_code == 200
    assert response.json() == [{"record": {"turn": 1}}]


def test_delete_session_404_when_missing(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=None)

    response = client.delete(f"/admin/sessions/{SESSION_ID}")

    assert response.status_code == 404


def test_delete_session_calls_service(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=_session())
    container.admin_service.delete_session = AsyncMock()

    response = client.delete(f"/admin/sessions/{SESSION_ID}")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}
    container.admin_service.delete_session.assert_awaited_once_with(SESSION_ID)


def test_block_user_removes_telegram_id_and_persists(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_user = AsyncMock(return_value=_telegram_user())
    container.admin_service.list_user_sessions = AsyncMock(return_value=[])
    container.telegram_authorization.add_private_user("555")

    response = client.post(f"/admin/users/{USER_ID}/block")

    assert response.status_code == 200
    assert response.json()["is_blocked"] is True
    assert container.telegram_authorization.is_private_chat_authorized("555") is False
    reloaded = TelegramAuthorization.from_directory(tmp_path / "authorization")
    assert reloaded.is_private_chat_authorized("555") is False


def test_block_user_400_when_no_telegram_identity(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_user = AsyncMock(
        return_value=User(id=USER_ID, display_name="No Telegram")
    )

    response = client.post(f"/admin/users/{USER_ID}/block")

    assert response.status_code == 400


def test_unblock_user_restores_access(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_user = AsyncMock(return_value=_telegram_user())
    container.admin_service.list_user_sessions = AsyncMock(return_value=[])
    # container.telegram_authorization starts with an empty allowlist (fresh tmp_path dir).

    response = client.post(f"/admin/users/{USER_ID}/unblock")

    assert response.status_code == 200
    assert response.json()["is_blocked"] is False
    assert container.telegram_authorization.is_private_chat_authorized("555") is True
