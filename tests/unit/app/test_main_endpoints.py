from typing import Any, cast

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
