import pytest
from pydantic import ValidationError

from rp_engine.app.main import build_container
from rp_engine.infrastructure.config.settings import Settings
from rp_engine.infrastructure.postgres import (
    PostgresConversationStore,
)
from rp_engine.infrastructure.postgres.repositories import (
    PostgresScenarioDefinitionStore,
    PostgresScenarioSessionStore,
)
from rp_engine.infrastructure.storage import (
    JsonConversationStore,
    JsonScenarioDefinitionStore,
    JsonScenarioSessionStore,
)


def test_missing_telegram_token_raises_clear_error() -> None:
    settings = Settings(telegram_enabled=True, telegram_bot_token="")

    with pytest.raises(ValueError, match="RP_ENGINE_TELEGRAM_BOT_TOKEN must be set"):
        build_container(settings)


def test_telegram_admin_user_id_is_stripped() -> None:
    settings = Settings(telegram_admin_user_id=" 12345 ")

    assert settings.telegram_admin_user_id == "12345"


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


def test_lmstudio_max_tokens_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        Settings(lmstudio_max_tokens=-1)


def test_lmstudio_max_tokens_zero_means_unlimited() -> None:
    assert Settings(lmstudio_max_tokens=0).lmstudio_max_tokens == 0


def test_lmstudio_max_tokens_empty_string_means_unlimited() -> None:
    assert Settings(lmstudio_max_tokens="").lmstudio_max_tokens == 0  # type: ignore[arg-type]


def test_lmstudio_temperature_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        Settings(lmstudio_temperature=-0.1)


def test_telegram_message_max_length_rejects_non_positive_values() -> None:
    with pytest.raises(ValidationError):
        Settings(telegram_message_max_length=0)


def test_invalid_debug_generation_trace_mode_fails_validation() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"debug_generation_trace": "verbose"})


def test_default_unauthorized_message_mentions_beta_request() -> None:
    settings = Settings()

    assert "closed beta" in settings.telegram_unauthorized_message
    assert "/beta" in settings.telegram_unauthorized_message


def test_persistence_backend_defaults_to_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RP_ENGINE_PERSISTENCE_BACKEND", raising=False)
    # Bypasses the developer's local .env (which may pin a backend for local dev); this
    # tests the code-level default, not the ambient environment. `_env_file` is a real
    # pydantic-settings override that the (unused here) mypy stubs don't know about.
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.persistence_backend == "json"


def test_build_container_uses_json_stores_by_default() -> None:
    settings = Settings(telegram_enabled=False, persistence_backend="json")

    container = build_container(settings)

    assert isinstance(container.chat_service._conversation_store, JsonConversationStore)
    assert isinstance(container.chat_service._scenario_session_store, JsonScenarioSessionStore)
    assert isinstance(
        container.chat_service._scenario_definition_store, JsonScenarioDefinitionStore
    )


def test_build_container_uses_postgres_stores_when_enabled() -> None:
    settings = Settings(
        telegram_enabled=False,
        persistence_backend="postgres",
    )

    container = build_container(settings)

    assert isinstance(container.chat_service._conversation_store, PostgresConversationStore)
    assert isinstance(container.chat_service._scenario_session_store, PostgresScenarioSessionStore)
    assert isinstance(
        container.chat_service._scenario_definition_store, PostgresScenarioDefinitionStore
    )


def test_empty_postgres_host_fails_validation() -> None:
    with pytest.raises(ValidationError, match="RP_ENGINE_POSTGRES_HOST must not be empty"):
        Settings(postgres_host="   ")


def test_scenario_catalog_dirs_defaults_to_data_catalog() -> None:
    # _env_file=None isolates this from the developer's local .env, which may set
    # RP_ENGINE_SCENARIO_CATALOG_DIRS for real use.
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.scenario_catalog_dirs == ["data/catalog"]


def test_scenario_catalog_dirs_parses_comma_delimited_string() -> None:
    settings = Settings(scenario_catalog_dirs="data/catalog, data/catalog-local")  # type: ignore[arg-type]

    assert settings.scenario_catalog_dirs == ["data/catalog", "data/catalog-local"]


def test_scenario_catalog_dirs_accepts_a_list() -> None:
    settings = Settings(scenario_catalog_dirs=["data/catalog", "data/catalog-local"])

    assert settings.scenario_catalog_dirs == ["data/catalog", "data/catalog-local"]


def test_scenario_catalog_dirs_rejects_empty_value() -> None:
    with pytest.raises(ValidationError, match="RP_ENGINE_SCENARIO_CATALOG_DIRS must not be empty"):
        Settings(scenario_catalog_dirs="")  # type: ignore[arg-type]
