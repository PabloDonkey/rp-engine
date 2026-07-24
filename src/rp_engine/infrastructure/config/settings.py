from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_TELEGRAM_UNAUTHORIZED_MESSAGE = (
    "This bot is currently in closed beta, and you are not authorized yet. "
    "Use /beta to request access. "
    "If you do, your Telegram username and ID will be recorded for administrator review."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RP_ENGINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RP Engine"
    app_environment: Literal["development", "test", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    persistence_backend: Literal["json", "postgres"] = "json"
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_database: str = "rp_engine"
    postgres_user: str = "rp_engine"
    postgres_password: str = "change_me"
    postgres_ssl_mode: Literal["disable", "require"] = "disable"
    postgres_pool_size: int = Field(default=10, ge=1)
    postgres_max_overflow: int = Field(default=10, ge=0)
    # Whether an unreachable Postgres at startup (persistence_backend="postgres") aborts
    # boot. When False, startup logs the failure and continues; /health then reports
    # db: unavailable rather than crashing the process.
    postgres_startup_check_fail_fast: bool = True

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_admin_user_id: str = ""
    telegram_authorization_dir: str = "data/telegram/authorization"
    telegram_unauthorized_message: str = DEFAULT_TELEGRAM_UNAUTHORIZED_MESSAGE
    telegram_message_max_length: int = Field(default=3800, ge=1)

    lmstudio_api_host: str = "localhost:1234"
    lmstudio_model: str = "qwen/qwen3-4b-2507"
    # Maximum tokens per reply. 0 means "no limit" (generate until the model stops or the
    # context is full). Absent or empty in the environment is treated as 0.
    lmstudio_max_tokens: int = Field(default=0, ge=0)
    lmstudio_temperature: float = Field(default=0.8, ge=0.0)
    lmstudio_top_k_sampling: int = Field(default=40, ge=1)
    lmstudio_repeat_penalty: float = Field(default=1.1, ge=0.0)
    lmstudio_top_p_sampling: float = Field(default=0.95, ge=0.0, le=1.0)
    lmstudio_min_p_sampling: float = Field(default=0.05, ge=0.0, le=1.0)

    debug_status_enabled: bool = False
    debug_generation_trace: Literal["off", "errors", "all"] = "off"
    default_world_id: str = "default"
    # Comma-delimited list of catalog directories, merged in order (later dirs win on
    # scenario id collisions). See ScenarioCatalog.from_directories.
    # NoDecode: pydantic-settings otherwise tries to JSON-parse a list-typed env var
    # before our field_validator runs, which rejects a plain comma-delimited string.
    scenario_catalog_dirs: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["data/catalog"]
    )

    @field_validator("lmstudio_max_tokens", mode="before")
    @classmethod
    def _empty_max_tokens_means_unlimited(cls, value: object) -> object:
        # An absent variable already falls back to the default (0); this also maps an
        # explicitly empty value (RP_ENGINE_LMSTUDIO_MAX_TOKENS=) to 0 rather than failing.
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return 0
        return value

    @field_validator("lmstudio_api_host")
    @classmethod
    def validate_lmstudio_api_host(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            msg = "RP_ENGINE_LMSTUDIO_API_HOST must not be empty."
            raise ValueError(msg)
        if ":" not in cleaned:
            msg = "RP_ENGINE_LMSTUDIO_API_HOST must be in host:port format."
            raise ValueError(msg)
        return cleaned

    @field_validator("lmstudio_model")
    @classmethod
    def validate_lmstudio_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("RP_ENGINE_LMSTUDIO_MODEL must not be empty.")
        return cleaned

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("telegram_unauthorized_message")
    @classmethod
    def validate_telegram_unauthorized_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("RP_ENGINE_TELEGRAM_UNAUTHORIZED_MESSAGE must not be empty.")
        return cleaned

    @field_validator("telegram_admin_user_id")
    @classmethod
    def validate_telegram_admin_user_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("default_world_id")
    @classmethod
    def validate_default_world_id(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("RP_ENGINE_DEFAULT_WORLD_ID must not be empty.")
        return cleaned

    @field_validator("persistence_backend")
    @classmethod
    def validate_persistence_backend(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("postgres_host")
    @classmethod
    def validate_postgres_host(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("RP_ENGINE_POSTGRES_HOST must not be empty.")
        return cleaned

    @field_validator("postgres_database")
    @classmethod
    def validate_postgres_database(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("RP_ENGINE_POSTGRES_DATABASE must not be empty.")
        return cleaned

    @field_validator("postgres_user")
    @classmethod
    def validate_postgres_user(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("RP_ENGINE_POSTGRES_USER must not be empty.")
        return cleaned

    @field_validator("postgres_password")
    @classmethod
    def validate_postgres_password(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("RP_ENGINE_POSTGRES_PASSWORD must not be empty.")
        return cleaned

    @field_validator("debug_generation_trace")
    @classmethod
    def validate_debug_generation_trace(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("scenario_catalog_dirs", mode="before")
    @classmethod
    def _split_scenario_catalog_dirs(cls, value: object) -> object:
        # pydantic-settings would otherwise require a JSON array for a list-typed env var;
        # accept a comma-delimited string instead (e.g. "data/catalog,data/catalog-local").
        if isinstance(value, str):
            return [entry.strip() for entry in value.split(",") if entry.strip()]
        return value

    @field_validator("scenario_catalog_dirs")
    @classmethod
    def validate_scenario_catalog_dirs(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("RP_ENGINE_SCENARIO_CATALOG_DIRS must not be empty.")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
