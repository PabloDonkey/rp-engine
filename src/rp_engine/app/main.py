import logging
from dataclasses import dataclass

from fastapi import FastAPI

from rp_engine.adapters.api import create_router as create_api_router
from rp_engine.adapters.telegram.adapter import (
    TelegramAdapter,
    TelegramRuntime,
    create_telegram_application,
)
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.app.lifespan import create_lifespan
from rp_engine.app.runtime_state import RuntimeState
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.memory.dump_everything_strategy import DumpEverythingStrategy
from rp_engine.core.ports import LLMProvider
from rp_engine.core.services.character_service import CharacterService
from rp_engine.core.services.chat_service import ChatService
from rp_engine.core.services.group_identity_resolver import GroupIdentityResolver
from rp_engine.core.services.identity_resolver import IdentityResolver
from rp_engine.infrastructure.config.settings import Settings, get_settings
from rp_engine.infrastructure.llm.lmstudio.provider import LMStudioProvider
from rp_engine.infrastructure.storage import (
    JsonCharacterStore,
    JsonConversationStore,
    JsonGroupIdentityStore,
    JsonSessionStore,
    JsonUserIdentityStore,
    JsonWorldStore,
)

logger = logging.getLogger(__name__)


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    llm_provider: LLMProvider
    orchestrator: RPOrchestrator
    chat_service: ChatService
    identity_resolver: IdentityResolver
    group_identity_resolver: GroupIdentityResolver
    character_service: CharacterService
    telegram_runtime: TelegramRuntime | None
    runtime_state: RuntimeState


def build_container(settings: Settings) -> AppContainer:
    logger.info("Environment loaded", extra={"app_environment": settings.app_environment})

    llm_provider = LMStudioProvider(
        model_name=settings.lmstudio_model,
        api_host=settings.lmstudio_api_host,
        max_tokens=settings.lmstudio_max_tokens,
        temperature=settings.lmstudio_temperature,
    )
    conversation_store = JsonConversationStore()
    user_identity_store = JsonUserIdentityStore()
    group_identity_store = JsonGroupIdentityStore()
    character_store = JsonCharacterStore()
    world_store = JsonWorldStore()
    session_store = JsonSessionStore()
    identity_resolver = IdentityResolver(store=user_identity_store)
    group_identity_resolver = GroupIdentityResolver(store=group_identity_store)
    character_service = CharacterService(
        character_store=character_store,
        world_store=world_store,
        session_store=session_store,
        default_world_id=settings.default_world_id,
    )
    memory_strategy = DumpEverythingStrategy()
    generation_settings = GenerationSettings(
        temperature=settings.lmstudio_temperature,
        max_tokens=settings.lmstudio_max_tokens,
        top_p=settings.lmstudio_top_p_sampling,
    )
    logger.info("LM Studio provider initialized", extra={"api_host": settings.lmstudio_api_host})
    orchestrator = RPOrchestrator(llm_provider=llm_provider)
    chat_service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_strategy=memory_strategy,
        user_identity_store=user_identity_store,
        group_identity_store=group_identity_store,
        session_store=session_store,
        character_store=character_store,
        world_store=world_store,
        generation_settings=generation_settings,
    )

    telegram_runtime: TelegramRuntime | None = None
    if settings.telegram_enabled:
        if not settings.telegram_bot_token:
            logger.error("Configuration error", extra={"field": "telegram_bot_token"})
            raise ValueError("RP_ENGINE_TELEGRAM_BOT_TOKEN must be set when Telegram is enabled.")

        telegram_adapter = TelegramAdapter(
            chat_service=chat_service,
            identity_resolver=identity_resolver,
            group_identity_resolver=group_identity_resolver,
            character_service=character_service,
            authorization=TelegramAuthorization.from_directory(
                settings.telegram_authorization_dir
            ),
            unauthorized_message=settings.telegram_unauthorized_message,
            message_max_length=settings.telegram_message_max_length,
        )
        telegram_application = create_telegram_application(
            token=settings.telegram_bot_token,
            adapter=telegram_adapter,
        )
        telegram_runtime = TelegramRuntime(application=telegram_application)
        logger.info("Telegram adapter enabled")
    else:
        logger.info("Telegram adapter disabled")

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
        identity_resolver=identity_resolver,
        group_identity_resolver=group_identity_resolver,
        character_service=character_service,
        telegram_runtime=telegram_runtime,
        runtime_state=RuntimeState(),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings if settings is not None else get_settings()
    configure_logging(resolved_settings.log_level)
    logger.info("Starting RP Engine")
    container = build_container(resolved_settings)

    app = FastAPI(title=resolved_settings.app_name, lifespan=create_lifespan(container))
    app.state.container = container
    app.include_router(create_api_router(container.chat_service))

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
