from typing import Any, TypedDict, cast
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from rp_engine.app.main import create_app
from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.postgres import PostgresConfig


class _UnreachablePostgresSettings(TypedDict):
    postgres_host: str
    postgres_port: int


class _UnreachablePostgresNoFailFastSettings(_UnreachablePostgresSettings):
    postgres_startup_check_fail_fast: bool


# Nothing listens on port 1 (a reserved/privileged port), so connecting here fails fast
# with "connection refused" instead of hanging or requiring a real Postgres in unit tests.
_UNREACHABLE_POSTGRES_SETTINGS: _UnreachablePostgresSettings = {
    "postgres_host": "127.0.0.1",
    "postgres_port": 1,
}

# Same, but with fail-fast disabled — for tests below that don't care about DB status at
# all, so they stay fast, pure unit tests rather than needing the testcontainers fixture.
# Spelled out rather than spread from the dict above: a TypedDict literal cannot be built
# by unpacking another one.
_UNREACHABLE_POSTGRES_NO_FAIL_FAST_SETTINGS: _UnreachablePostgresNoFailFastSettings = {
    "postgres_host": "127.0.0.1",
    "postgres_port": 1,
    "postgres_startup_check_fail_fast": False,
}


def test_health_endpoint_reports_service_statuses(postgres_config: PostgresConfig) -> None:
    settings = Settings(
        telegram_enabled=False,
        postgres_host=postgres_config.host,
        postgres_port=postgres_config.port,
        postgres_database=postgres_config.database,
        postgres_user=postgres_config.user,
        postgres_password=postgres_config.password,
    )
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
            "db": "available",
        },
    }


def test_postgres_backend_fails_fast_at_startup_when_db_unreachable() -> None:
    settings = Settings(telegram_enabled=False, **_UNREACHABLE_POSTGRES_SETTINGS)
    app = create_app(settings)

    with pytest.raises(RuntimeError, match="unreachable"), TestClient(app):
        pass


def test_postgres_backend_health_reports_unavailable_when_fail_fast_disabled() -> None:
    settings = Settings(telegram_enabled=False, **_UNREACHABLE_POSTGRES_NO_FAIL_FAST_SETTINGS)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["services"]["db"] == "unavailable"


def test_debug_status_endpoint_disabled_by_default() -> None:
    settings = Settings(debug_status_enabled=False, **_UNREACHABLE_POSTGRES_NO_FAIL_FAST_SETTINGS)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/debug/status")

    assert response.status_code == 404


def test_debug_status_endpoint_returns_runtime_state_when_enabled() -> None:
    settings = Settings(
        debug_status_enabled=True,
        telegram_enabled=False,
        **_UNREACHABLE_POSTGRES_NO_FAIL_FAST_SETTINGS,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/debug/status")

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["model_name"] == settings.lmstudio_model
    assert payload["application_state"] == "running"
    assert payload["enabled_adapters"] == []


def test_chat_endpoint_calls_send_message_use_case() -> None:
    settings = Settings(telegram_enabled=False, **_UNREACHABLE_POSTGRES_NO_FAIL_FAST_SETTINGS)
    app = create_app(settings)
    app.state.container.chat_service.send_message = AsyncMock(return_value="hello")

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "owner_kind": "session",
                "owner_id": "00000000-0000-0000-0000-000000000001",
                "message": "hi",
            },
        )

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload == {"response": "hello"}


def test_continue_endpoint_calls_continue_story_use_case() -> None:
    settings = Settings(telegram_enabled=False, **_UNREACHABLE_POSTGRES_NO_FAIL_FAST_SETTINGS)
    app = create_app(settings)
    app.state.container.chat_service.continue_story = AsyncMock(return_value="next")

    with TestClient(app) as client:
        response = client.post(
            "/continue",
            json={
                "owner_kind": "session",
                "owner_id": "00000000-0000-0000-0000-000000000001",
            },
        )

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload == {"response": "next"}


def test_memory_clear_endpoint_calls_clear_conversation_use_case() -> None:
    settings = Settings(telegram_enabled=False, **_UNREACHABLE_POSTGRES_NO_FAIL_FAST_SETTINGS)
    app = create_app(settings)
    app.state.container.chat_service.clear_conversation = AsyncMock()

    with TestClient(app) as client:
        response = client.post(
            "/memory/clear",
            json={
                "owner_kind": "session",
                "owner_id": "00000000-0000-0000-0000-000000000001",
            },
        )

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload == {"status": "cleared"}
