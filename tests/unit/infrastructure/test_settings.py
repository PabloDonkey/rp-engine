import pytest
from pydantic import ValidationError

from rp_engine.app.main import build_container
from rp_engine.infrastructure.config.settings import Settings


def test_missing_telegram_token_raises_clear_error() -> None:
    settings = Settings(telegram_enabled=True, telegram_bot_token="")

    with pytest.raises(ValueError, match="RP_ENGINE_TELEGRAM_BOT_TOKEN must be set"):
        build_container(settings)


def test_missing_lmstudio_host_fails_validation() -> None:
    with pytest.raises(ValidationError, match="RP_ENGINE_LMSTUDIO_API_HOST must not be empty"):
        Settings(lmstudio_api_host="")


def test_invalid_lmstudio_host_format_fails_validation() -> None:
    with pytest.raises(ValidationError, match="host:port format"):
        Settings(lmstudio_api_host="localhost")


def test_missing_lmstudio_model_fails_validation() -> None:
    with pytest.raises(ValidationError, match="RP_ENGINE_LMSTUDIO_MODEL must not be empty"):
        Settings(lmstudio_model="   ")


def test_invalid_port_fails_validation() -> None:
    with pytest.raises(ValidationError):
        Settings(app_port=70000)


def test_development_mode_allows_running_without_telegram() -> None:
    settings = Settings(app_environment="development", telegram_enabled=False)

    container = build_container(settings)

    assert container.telegram_runtime is None


def test_empty_telegram_unauthorized_message_fails_validation() -> None:
    with pytest.raises(ValidationError, match="RP_ENGINE_TELEGRAM_UNAUTHORIZED_MESSAGE"):
        Settings(telegram_unauthorized_message="   ")


def test_lmstudio_max_tokens_rejects_non_positive_values() -> None:
    with pytest.raises(ValidationError):
        Settings(lmstudio_max_tokens=0)


def test_lmstudio_temperature_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        Settings(lmstudio_temperature=-0.1)
