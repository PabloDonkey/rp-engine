import logging
from dataclasses import dataclass

from fastapi import FastAPI

from rp_engine.adapters.telegram.adapter import (
    TelegramAdapter,
    TelegramRuntime,
    create_telegram_application,
)
from rp_engine.app.lifespan import create_lifespan
from rp_engine.app.runtime_state import RuntimeState
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.ports import LLMProvider
from rp_engine.core.services.chat_service import ChatService
from rp_engine.infrastructure.config.settings import Settings, get_settings
from rp_engine.infrastructure.llm.lmstudio_provider import LMStudioProvider

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    llm_provider: LLMProvider
    orchestrator: RPOrchestrator
    chat_service: ChatService
    telegram_runtime: TelegramRuntime | None
    runtime_state: RuntimeState


def build_container(settings: Settings) -> AppContainer:
    logger.info("Configuration loaded", extra={"app_environment": settings.app_environment})

    llm_provider = LMStudioProvider(
        model_name=settings.lmstudio_model,
        api_host=settings.lmstudio_api_host,
    )
    orchestrator = RPOrchestrator(llm_provider=llm_provider)
    chat_service = ChatService(orchestrator=orchestrator)

    telegram_runtime: TelegramRuntime | None = None
    if settings.telegram_enabled:
        if not settings.telegram_bot_token:
            logger.error("Configuration error", extra={"field": "telegram_bot_token"})
            raise ValueError("RP_ENGINE_TELEGRAM_BOT_TOKEN must be set when Telegram is enabled.")

        telegram_adapter = TelegramAdapter(chat_service=chat_service)
        telegram_application = create_telegram_application(
            token=settings.telegram_bot_token,
            adapter=telegram_adapter,
        )
        telegram_runtime = TelegramRuntime(application=telegram_application)

    logger.info(
        "Dependencies created",
        extra={
            "telegram_enabled": settings.telegram_enabled,
            "lmstudio_model": settings.lmstudio_model,
        },
    )

    return AppContainer(
        settings=settings,
        llm_provider=llm_provider,
        orchestrator=orchestrator,
        chat_service=chat_service,
        telegram_runtime=telegram_runtime,
        runtime_state=RuntimeState(),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings if settings is not None else get_settings()
    logger.info("Application starting")
    container = build_container(resolved_settings)

    app = FastAPI(title=resolved_settings.app_name, lifespan=create_lifespan(container))
    app.state.container = container

    @app.get("/health")
    async def health() -> dict[str, object]:
        llm_status = "available" if container.settings.lmstudio_model else "unavailable"
        telegram_status = "running" if container.telegram_runtime is not None else "disabled"
        return {
            "status": "ok",
            "services": {
                "llm": llm_status,
                "telegram": telegram_status,
            },
        }

    if resolved_settings.debug_status_enabled:

        @app.get("/debug/status")
        async def debug_status() -> dict[str, object]:
            enabled_adapters = ["telegram"] if container.telegram_runtime is not None else []
            return {
                "model_name": container.settings.lmstudio_model,
                "application_state": container.runtime_state.app_state,
                "enabled_adapters": enabled_adapters,
            }

    return app


app = create_app()
