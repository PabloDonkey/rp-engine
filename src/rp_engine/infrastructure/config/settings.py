from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_TELEGRAM_UNAUTHORIZED_MESSAGE = (
    "Hi! \U0001f44b This bot is currently in a private beta and isn't accepting new users yet. "
    "If you'd like access, please contact @pablodonkey on Telegram. Thanks for your interest!"
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

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_authorization_dir: str = "data/telegram/authorization"
    telegram_unauthorized_message: str = DEFAULT_TELEGRAM_UNAUTHORIZED_MESSAGE
    telegram_message_max_length: int = Field(default=3800, ge=1)

    lmstudio_api_host: str = "localhost:1234"
    lmstudio_model: str = "qwen/qwen3-4b-2507"
    lmstudio_max_tokens: int = Field(default=600, ge=1)
    lmstudio_temperature: float = Field(default=0.8, ge=0.0)
    lmstudio_top_k_sampling: int = Field(default=40, ge=1)
    lmstudio_repeat_penalty: float = Field(default=1.1, ge=0.0)
    lmstudio_top_p_sampling: float = Field(default=0.95, ge=0.0, le=1.0)
    lmstudio_min_p_sampling: float = Field(default=0.05, ge=0.0, le=1.0)

    debug_status_enabled: bool = False

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
