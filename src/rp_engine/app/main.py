from dataclasses import dataclass

from fastapi import FastAPI

from rp_engine.adapters.telegram.adapter import (
    TelegramAdapter,
    TelegramRuntime,
    create_telegram_application,
)
from rp_engine.app.lifespan import create_lifespan
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.services.chat_service import ChatService
from rp_engine.infrastructure.config.settings import Settings, get_settings
from rp_engine.infrastructure.llm.lmstudio_provider import LMStudioProvider


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    llm_provider: LMStudioProvider
    orchestrator: RPOrchestrator
    chat_service: ChatService
    telegram_runtime: TelegramRuntime | None


def build_container(settings: Settings) -> AppContainer:
    llm_provider = LMStudioProvider(
        model_name=settings.lmstudio_model,
        api_host=settings.lmstudio_api_host,
    )
    orchestrator = RPOrchestrator(llm_provider=llm_provider)
    chat_service = ChatService(orchestrator=orchestrator)

    telegram_runtime: TelegramRuntime | None = None
    if settings.telegram_enabled:
        if not settings.telegram_bot_token:
            raise ValueError("RP_ENGINE_TELEGRAM_BOT_TOKEN must be set when Telegram is enabled.")

        telegram_adapter = TelegramAdapter(chat_service=chat_service)
        telegram_application = create_telegram_application(
            token=settings.telegram_bot_token,
            adapter=telegram_adapter,
        )
        telegram_runtime = TelegramRuntime(application=telegram_application)

    return AppContainer(
        settings=settings,
        llm_provider=llm_provider,
        orchestrator=orchestrator,
        chat_service=chat_service,
        telegram_runtime=telegram_runtime,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings if settings is not None else get_settings()
    container = build_container(resolved_settings)

    app = FastAPI(title=resolved_settings.app_name, lifespan=create_lifespan(container))
    app.state.container = container

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
