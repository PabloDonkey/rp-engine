from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.app.main import create_app
from rp_engine.application.services.admin_service import AdminDeletedMessage, AdminUserSummary
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.scenario.session_directives import SessionDirectives
from rp_engine.core.user.identity import UserIdentity
from rp_engine.core.user.user import User
from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.scenario_transfer import SYSTEM_OWNER_ID

USER_ID = UUID("00000000-0000-0000-0000-000000000042")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000999")


def _setup(tmp_path: Path) -> tuple[TestClient, Any]:
    settings = Settings(
        telegram_enabled=False,
        telegram_authorization_dir=str(tmp_path / "authorization"),
        # Nothing listens on port 1, so this fails fast instead of needing a real DB —
        # every test here mocks `admin_service` directly and never touches Postgres.
        postgres_host="127.0.0.1",
        postgres_port=1,
        postgres_startup_check_fail_fast=False,
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


def _scenario(scenario_id: str = "vault", *, name: str = "Vault") -> ScenarioDefinition:
    return ScenarioDefinition(
        id=scenario_id, owner_id=SYSTEM_OWNER_ID, name=name, description="A vault."
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


def test_get_session_exposes_directives(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    directives, _ = SessionDirectives().with_language("fr").with_rule("No time skips.")
    container.admin_service.get_session = AsyncMock(
        return_value=_session().with_directives(
            directives.with_director_instruction("Raise the stakes.")
        )
    )
    container.admin_service.get_session_transcript = AsyncMock(return_value=[])

    response = client.get(f"/admin/sessions/{SESSION_ID}")

    assert response.status_code == 200
    assert response.json()["directives"] == {
        "language": "fr",
        "rules": [{"id": "1", "text": "No time skips."}],
        "director_instruction": "Raise the stakes.",
    }


def test_get_session_reports_default_directives(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=_session())
    container.admin_service.get_session_transcript = AsyncMock(return_value=[])

    response = client.get(f"/admin/sessions/{SESSION_ID}")

    assert response.json()["directives"] == {
        "language": "auto",
        "rules": [],
        "director_instruction": "",
    }


def test_get_session_exposes_the_persona_and_lifecycle(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(
        return_value=_session().with_persona(name="Sera Vane", description="A wary courier.")
    )
    container.admin_service.get_session_transcript = AsyncMock(return_value=[])

    body = client.get(f"/admin/sessions/{SESSION_ID}").json()

    assert body["user_persona_name"] == "Sera Vane"
    assert body["user_persona_description"] == "A wary courier."
    assert body["deleted_at"] is None
    assert body["updated_at"]


def test_set_session_persona_fills_in_a_missing_one(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    session = _session()
    container.admin_service.get_session = AsyncMock(return_value=session)
    container.admin_service.set_session_persona = AsyncMock(
        return_value=session.with_persona(name="Sera Vane", description="A wary courier.")
    )
    container.admin_service.get_session_transcript = AsyncMock(return_value=[])

    response = client.put(
        f"/admin/sessions/{SESSION_ID}/persona",
        json={"name": "Sera Vane", "description": "A wary courier."},
    )

    assert response.status_code == 200
    assert response.json()["user_persona_name"] == "Sera Vane"
    container.admin_service.set_session_persona.assert_awaited_once()


def test_set_session_persona_replaces_an_existing_one(tmp_path: Path) -> None:
    """The admin exception to ADR-025: a player can only change a persona with /clear, an
    operator looking at the whole session can correct one in place."""
    client, container = _setup(tmp_path)
    session = _session().with_persona(name="Sera Vane")
    container.admin_service.get_session = AsyncMock(return_value=session)
    container.admin_service.set_session_persona = AsyncMock(
        return_value=session.override_persona(name="Sera Vayne", description="Fixed typo.")
    )
    container.admin_service.get_session_transcript = AsyncMock(return_value=[])

    response = client.put(
        f"/admin/sessions/{SESSION_ID}/persona",
        json={"name": "Sera Vayne", "description": "Fixed typo."},
    )

    assert response.status_code == 200
    assert response.json()["user_persona_name"] == "Sera Vayne"


def test_set_session_persona_409_for_a_superseded_session(tmp_path: Path) -> None:
    # Nothing set here would ever reach a prompt again, so it is refused rather than
    # silently accepted as a no-op.
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=_session().mark_deleted())
    container.admin_service.set_session_persona = AsyncMock()

    response = client.put(f"/admin/sessions/{SESSION_ID}/persona", json={"name": "Sera Vane"})

    assert response.status_code == 409
    container.admin_service.set_session_persona.assert_not_awaited()


def test_set_session_persona_400_on_a_blank_name(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=_session())
    container.admin_service.set_session_persona = AsyncMock()

    response = client.put(f"/admin/sessions/{SESSION_ID}/persona", json={"name": "   "})

    assert response.status_code == 400
    container.admin_service.set_session_persona.assert_not_awaited()


def test_import_session_409_when_the_owner_already_has_a_live_one(tmp_path: Path) -> None:
    """Migration 0010 makes one live session per owner+scenario a database invariant, so a
    conflicting import is refused rather than recreating the duplicate that made `/play`
    resurrect old stories."""
    client, container = _setup(tmp_path)
    container.scenario_transfer_service.import_session = AsyncMock(
        side_effect=IntegrityError("stmt", {}, Exception("duplicate key"))
    )

    response = client.post("/admin/sessions/import", json={"session": {}, "transcript": []})

    assert response.status_code == 409
    assert "already has a live session" in response.json()["detail"]


def test_set_session_persona_404_when_the_session_is_missing(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=None)

    response = client.put(f"/admin/sessions/{SESSION_ID}/persona", json={"name": "Sera Vane"})

    assert response.status_code == 404


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


def test_list_scenarios_returns_summaries(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.list_scenarios = AsyncMock(return_value=[_scenario()])

    response = client.get("/admin/scenarios")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "vault", "name": "Vault", "description": "A vault.", "visibility": "PUBLIC"}
    ]


def test_get_scenario_404_when_missing(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_scenario = AsyncMock(return_value=None)

    response = client.get("/admin/scenarios/nope")

    assert response.status_code == 404


def test_get_scenario_returns_full_payload(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_scenario = AsyncMock(return_value=_scenario())

    response = client.get("/admin/scenarios/vault")

    assert response.status_code == 200
    assert response.json()["id"] == "vault"
    assert response.json()["name"] == "Vault"


def test_create_scenario_409_when_id_exists(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_scenario = AsyncMock(return_value=_scenario())

    response = client.post("/admin/scenarios", json={"id": "vault"})

    assert response.status_code == 409


def test_create_scenario_422_on_invalid_payload(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_scenario = AsyncMock(return_value=None)
    container.scenario_transfer_service.import_scenario_payload = AsyncMock(return_value=None)

    response = client.post("/admin/scenarios", json={"id": "vault"})

    assert response.status_code == 422


def test_create_scenario_succeeds(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_scenario = AsyncMock(return_value=None)
    container.scenario_transfer_service.import_scenario_payload = AsyncMock(
        return_value=_scenario()
    )

    response = client.post("/admin/scenarios", json={"id": "vault"})

    assert response.status_code == 201
    assert response.json()["id"] == "vault"


def test_update_scenario_404_when_missing(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_scenario = AsyncMock(return_value=None)

    response = client.put("/admin/scenarios/vault", json={"id": "vault"})

    assert response.status_code == 404


def test_update_scenario_400_when_id_mismatch(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_scenario = AsyncMock(return_value=_scenario())

    response = client.put("/admin/scenarios/vault", json={"id": "different"})

    assert response.status_code == 400


def test_update_scenario_succeeds(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_scenario = AsyncMock(return_value=_scenario())
    container.scenario_transfer_service.import_scenario_payload = AsyncMock(
        return_value=_scenario(name="Renamed Vault")
    )

    response = client.put("/admin/scenarios/vault", json={"id": "vault"})

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Vault"


def test_import_scenario_422_on_invalid_payload(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.scenario_transfer_service.import_scenario_payload = AsyncMock(return_value=None)

    response = client.post("/admin/scenarios/import", json={"id": "vault"})

    assert response.status_code == 422


def test_export_session_404_when_missing(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.scenario_transfer_service.export_session = AsyncMock(return_value=None)

    response = client.get(f"/admin/sessions/{SESSION_ID}/export")

    assert response.status_code == 404


def test_export_session_returns_payload(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    exported = {"session": {"id": str(SESSION_ID)}, "transcript": []}
    container.scenario_transfer_service.export_session = AsyncMock(return_value=exported)

    response = client.get(f"/admin/sessions/{SESSION_ID}/export")

    assert response.status_code == 200
    assert response.json() == exported


def test_import_session_422_on_invalid_payload(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.scenario_transfer_service.import_session = AsyncMock(return_value=None)

    response = client.post("/admin/sessions/import", json={"session": {}})

    assert response.status_code == 422


def test_import_session_succeeds(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.scenario_transfer_service.import_session = AsyncMock(return_value=_session())

    response = client.post("/admin/sessions/import", json={"session": {}, "transcript": []})

    assert response.status_code == 200
    assert response.json()["id"] == str(SESSION_ID)


def test_delete_last_message_returns_the_removed_message(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=_session())
    container.admin_service.delete_last_message = AsyncMock(
        return_value=AdminDeletedMessage(
            message=ConversationMessage(
                role=ConversationRole.CHARACTER, content="bad turn", metadata={"turn": "10"}
            ),
            deleted_traces=2,
        )
    )

    response = client.delete(f"/admin/sessions/{SESSION_ID}/messages/last")

    assert response.status_code == 200
    assert response.json() == {
        "message": {
            "role": "character",
            "content": "bad turn",
            "metadata": {"turn": "10"},
        },
        # A retried turn has more than one trace; all of them describe a turn that no
        # longer exists.
        "deleted_traces": 2,
    }


def test_delete_last_message_404_when_session_missing(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=None)
    container.admin_service.delete_last_message = AsyncMock()

    response = client.delete(f"/admin/sessions/{SESSION_ID}/messages/last")

    assert response.status_code == 404
    container.admin_service.delete_last_message.assert_not_awaited()


def test_delete_last_message_404_when_conversation_is_empty(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=_session())
    container.admin_service.delete_last_message = AsyncMock(return_value=None)

    response = client.delete(f"/admin/sessions/{SESSION_ID}/messages/last")

    assert response.status_code == 404
