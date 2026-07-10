from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RP_ENGINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RP Engine"
    app_environment: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    telegram_enabled: bool = False
    telegram_bot_token: str = ""

    lmstudio_api_host: str = "localhost:1234"
    lmstudio_model: str = "qwen/qwen3-4b-2507"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
