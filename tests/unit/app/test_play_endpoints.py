"""The panel's play routes: send a turn, continue, retry.

Every test here mocks `chat_service` and `admin_service` directly. Nothing generates and
nothing touches Postgres — what is under test is the translation between the service's
answers and HTTP, which is the only thing these routes do.
"""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

from fastapi.testclient import TestClient

from rp_engine.app.main import create_app
from rp_engine.application.services.chat_service import SessionBusyError
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.llm.errors import LLMConnectionError
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.infrastructure.config.settings import Settings

USER_ID = UUID("00000000-0000-0000-0000-000000000042")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000999")


def _setup(tmp_path: Path) -> tuple[TestClient, Any]:
    settings = Settings(
        telegram_enabled=False,
        telegram_authorization_dir=str(tmp_path / "authorization"),
        # Nothing listens on port 1, so this fails fast instead of needing a real DB.
        postgres_host="127.0.0.1",
        postgres_port=1,
        postgres_startup_check_fail_fast=False,
    )
    app = create_app(settings)
    return TestClient(app), app.state.container


def _session(*, deleted: bool = False) -> ScenarioSession:
    session = ScenarioSession(
        id=SESSION_ID, scenario_definition_id="def-1", owner_kind="user", owner_id=USER_ID
    )
    if deleted:
        return replace(session, deleted_at=datetime(2026, 8, 1, tzinfo=UTC))
    return session


def _narrator_reply() -> ConversationMessage:
    return ConversationMessage(
        role=ConversationRole.CHARACTER,
        content="The lamp room smells of hot brass.",
        metadata={"turn": "24", "finish_reason": "length"},
    )


def _ready(container: Any, *, session: ScenarioSession | None = None) -> None:
    """A live session whose transcript ends with a narrator reply."""
    container.admin_service.get_session = AsyncMock(
        return_value=session if session is not None else _session()
    )
    container.admin_service.get_session_transcript = AsyncMock(return_value=[_narrator_reply()])


def test_send_turn_returns_the_stored_narrator_message(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    _ready(container)
    container.chat_service.send_message = AsyncMock(
        return_value="The lamp room smells of hot brass."
    )

    response = client.post(f"/admin/sessions/{SESSION_ID}/turn", json={"message": "I climb up"})

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    # The turn number and the finish reason ride along; the client needs the second one to
    # decide whether Continue offers to finish a cut-off sentence.
    assert payload == {
        "role": "character",
        "content": "The lamp room smells of hot brass.",
        "metadata": {"turn": "24", "finish_reason": "length"},
    }
    assert container.chat_service.send_message.await_args.kwargs["message"] == "I climb up"


def test_send_turn_404_when_the_session_is_missing(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=None)
    container.chat_service.send_message = AsyncMock()

    response = client.post(f"/admin/sessions/{SESSION_ID}/turn", json={"message": "hello"})

    assert response.status_code == 404
    container.chat_service.send_message.assert_not_awaited()


def test_send_turn_409_for_a_retired_session(tmp_path: Path) -> None:
    """A superseded story is readable and finished. It must not quietly come back to life."""
    client, container = _setup(tmp_path)
    container.admin_service.get_session = AsyncMock(return_value=_session(deleted=True))
    container.chat_service.send_message = AsyncMock()

    response = client.post(f"/admin/sessions/{SESSION_ID}/turn", json={"message": "hello"})

    assert response.status_code == 409
    assert "retired" in response.json()["detail"]
    container.chat_service.send_message.assert_not_awaited()


def test_send_turn_422_for_an_empty_message(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    _ready(container)
    container.chat_service.send_message = AsyncMock()

    response = client.post(f"/admin/sessions/{SESSION_ID}/turn", json={"message": "   "})

    assert response.status_code == 422
    container.chat_service.send_message.assert_not_awaited()


def test_turn_409_when_the_story_is_already_generating(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    _ready(container)
    container.chat_service.send_message = AsyncMock(
        side_effect=SessionBusyError("This story is already writing a reply.")
    )

    response = client.post(f"/admin/sessions/{SESSION_ID}/turn", json={"message": "hello"})

    assert response.status_code == 409
    assert response.json()["detail"] == "This story is already writing a reply."


def test_turn_502_when_the_model_fails(tmp_path: Path) -> None:
    """A model failure is not a bad request. The panel needs a reason, not a bare 500."""
    client, container = _setup(tmp_path)
    _ready(container)
    container.chat_service.send_message = AsyncMock(
        side_effect=LLMConnectionError("Unable to connect to LM Studio.")
    )

    response = client.post(f"/admin/sessions/{SESSION_ID}/turn", json={"message": "hello"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Unable to connect to LM Studio."


def test_continue_calls_continue_story(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    _ready(container)
    container.chat_service.continue_story = AsyncMock(return_value="the story advances")

    response = client.post(f"/admin/sessions/{SESSION_ID}/continue")

    assert response.status_code == 200
    container.chat_service.continue_story.assert_awaited_once()


def test_retry_calls_regenerate(tmp_path: Path) -> None:
    client, container = _setup(tmp_path)
    _ready(container)
    container.chat_service.regenerate_last_response = AsyncMock(return_value="a second attempt")

    response = client.post(f"/admin/sessions/{SESSION_ID}/retry")

    assert response.status_code == 200
    container.chat_service.regenerate_last_response.assert_awaited_once()


def test_retry_409_passes_the_services_own_reason(tmp_path: Path) -> None:
    """The service writes these sentences for the player. Show them, do not reword them."""
    client, container = _setup(tmp_path)
    _ready(container)
    container.chat_service.regenerate_last_response = AsyncMock(
        side_effect=ValueError(
            "Last message is not a character reply. Regenerate is not available yet."
        )
    )

    response = client.post(f"/admin/sessions/{SESSION_ID}/retry")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Last message is not a character reply. Regenerate is not available yet."
    )
