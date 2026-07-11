from typing import Any, cast
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from rp_engine.app.main import create_app
from rp_engine.infrastructure.config.settings import Settings


def test_health_endpoint_reports_service_statuses() -> None:
    settings = Settings(telegram_enabled=False)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload == {
        "status": "ok",
        "services": {
            "llm": "available",
            "telegram": "disabled",
        },
    }


def test_debug_status_endpoint_disabled_by_default() -> None:
    settings = Settings(debug_status_enabled=False)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/debug/status")

    assert response.status_code == 404


def test_debug_status_endpoint_returns_runtime_state_when_enabled() -> None:
    settings = Settings(debug_status_enabled=True, telegram_enabled=False)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/debug/status")

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["model_name"] == settings.lmstudio_model
    assert payload["application_state"] == "running"
    assert payload["enabled_adapters"] == []


def test_chat_endpoint_calls_send_message_use_case() -> None:
    settings = Settings(telegram_enabled=False)
    app = create_app(settings)
    app.state.container.chat_service.send_message = AsyncMock(return_value="hello")

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "owner_kind": "user",
                "owner_id": "42",
                "message": "hi",
            },
        )

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload == {"response": "hello"}


def test_continue_endpoint_calls_continue_story_use_case() -> None:
    settings = Settings(telegram_enabled=False)
    app = create_app(settings)
    app.state.container.chat_service.continue_story = AsyncMock(return_value="next")

    with TestClient(app) as client:
        response = client.post(
            "/continue",
            json={
                "owner_kind": "group",
                "owner_id": "-100",
            },
        )

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload == {"response": "next"}


def test_memory_clear_endpoint_calls_clear_conversation_use_case() -> None:
    settings = Settings(telegram_enabled=False)
    app = create_app(settings)
    app.state.container.chat_service.clear_conversation = AsyncMock()

    with TestClient(app) as client:
        response = client.post(
            "/memory/clear",
            json={
                "owner_kind": "user",
                "owner_id": "42",
            },
        )

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload == {"status": "cleared"}
