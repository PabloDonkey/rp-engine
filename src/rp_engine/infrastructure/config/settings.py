from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    telegram_enabled: bool = False
    telegram_bot_token: str = ""

    lmstudio_api_host: str = "localhost:1234"
    lmstudio_model: str = "qwen/qwen3-4b-2507"

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
