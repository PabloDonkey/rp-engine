import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from rp_engine.adapters.api import create_router as create_api_router
from rp_engine.adapters.telegram.adapter import (
    TelegramAdapter,
    TelegramRuntime,
    create_telegram_application,
)
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.adapters.telegram.narrator_store import TelegramNarratorStore
from rp_engine.app.lifespan import create_lifespan
from rp_engine.app.runtime_state import RuntimeState
from rp_engine.application.services.chat_service import ChatService
from rp_engine.application.services.group_identity_resolver import GroupIdentityResolver
from rp_engine.application.services.identity_resolver import IdentityResolver
from rp_engine.application.services.playthrough_service import PlaythroughService
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.memory.dump_everything_strategy import DumpEverythingStrategy
from rp_engine.core.ports import (
    ConversationStore,
    GenerationTraceStore,
    GroupIdentityStore,
    LLMProvider,
    ScenarioDefinitionStore,
    ScenarioSessionStore,
    UserIdentityStore,
)
from rp_engine.infrastructure.catalog import ScenarioCatalog
from rp_engine.infrastructure.config.settings import Settings, get_settings
from rp_engine.infrastructure.llm.lmstudio import LMStudioProvider
from rp_engine.infrastructure.postgres import (
    PostgresConfig,
    PostgresConversationStore,
    PostgresHealthProbe,
    create_engine,
    create_session_factory,
)
from rp_engine.infrastructure.postgres.repositories import (
    PostgresGenerationTraceStore,
    PostgresGroupIdentityStore,
    PostgresScenarioDefinitionStore,
    PostgresScenarioSessionStore,
    PostgresUserIdentityStore,
)
from rp_engine.infrastructure.storage import (
    JsonConversationStore,
    JsonGenerationTraceStore,
    JsonGroupIdentityStore,
    JsonScenarioDefinitionStore,
    JsonScenarioSessionStore,
    JsonUserIdentityStore,
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
    playthrough_service: PlaythroughService
    telegram_runtime: TelegramRuntime | None
    runtime_state: RuntimeState
    db_health_probe: PostgresHealthProbe | None
    db_startup_check_fail_fast: bool


def build_container(settings: Settings) -> AppContainer:
    logger.info("Environment loaded", extra={"app_environment": settings.app_environment})

    llm_provider = LMStudioProvider(
        model_name=settings.lmstudio_model,
        api_host=settings.lmstudio_api_host,
        max_tokens=settings.lmstudio_max_tokens,
        temperature=settings.lmstudio_temperature,
    )
    conversation_store: ConversationStore
    scenario_definition_store: ScenarioDefinitionStore
    scenario_session_store: ScenarioSessionStore
    generation_trace_store: GenerationTraceStore
    user_identity_store: UserIdentityStore
    group_identity_store: GroupIdentityStore
    db_health_probe: PostgresHealthProbe | None = None
    if settings.persistence_backend == "postgres":
        postgres_config = PostgresConfig.from_settings(settings)
        postgres_engine = create_engine(postgres_config)
        postgres_session_factory = create_session_factory(postgres_engine)
        conversation_store = PostgresConversationStore(postgres_session_factory)
        scenario_definition_store = PostgresScenarioDefinitionStore(postgres_session_factory)
        scenario_session_store = PostgresScenarioSessionStore(postgres_session_factory)
        generation_trace_store = PostgresGenerationTraceStore(postgres_session_factory)
        user_identity_store = PostgresUserIdentityStore(postgres_session_factory)
        group_identity_store = PostgresGroupIdentityStore(postgres_session_factory)
        db_health_probe = PostgresHealthProbe(
            postgres_engine, alembic_ini_path=Path.cwd() / "alembic.ini"
        )
    else:
        conversation_store = JsonConversationStore()
        scenario_definition_store = JsonScenarioDefinitionStore()
        scenario_session_store = JsonScenarioSessionStore()
        generation_trace_store = JsonGenerationTraceStore()
        user_identity_store = JsonUserIdentityStore()
        group_identity_store = JsonGroupIdentityStore()

    identity_resolver = IdentityResolver(store=user_identity_store)
    group_identity_resolver = GroupIdentityResolver(store=group_identity_store)
    scenario_catalog = ScenarioCatalog.from_directories(settings.scenario_catalog_dirs)
    playthrough_service = PlaythroughService(
        catalog=scenario_catalog,
        scenario_definition_store=scenario_definition_store,
        scenario_session_store=scenario_session_store,
        conversation_store=conversation_store,
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
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=generation_settings,
        generation_trace_store=generation_trace_store,
        generation_trace_mode=settings.debug_generation_trace,
    )

    telegram_runtime: TelegramRuntime | None = None
    if settings.telegram_enabled:
        if not settings.telegram_bot_token:
            logger.error("Configuration error", extra={"field": "telegram_bot_token"})
            raise ValueError("RP_ENGINE_TELEGRAM_BOT_TOKEN must be set when Telegram is enabled.")
        if not settings.telegram_admin_user_id:
            logger.warning(
                "Telegram admin user ID is not configured; hidden admin commands are disabled."
            )

        telegram_adapter = TelegramAdapter(
            chat_service=chat_service,
            identity_resolver=identity_resolver,
            group_identity_resolver=group_identity_resolver,
            playthrough_service=playthrough_service,
            authorization=TelegramAuthorization.from_directory(
                settings.telegram_authorization_dir,
                admin_user_id=settings.telegram_admin_user_id,
            ),
            admin_telegram_user_id=settings.telegram_admin_user_id,
            unauthorized_message=settings.telegram_unauthorized_message,
            message_max_length=settings.telegram_message_max_length,
            narrator_store=TelegramNarratorStore(),
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
            "persistence_backend": settings.persistence_backend,
        },
    )

    return AppContainer(
        settings=settings,
        llm_provider=llm_provider,
        orchestrator=orchestrator,
        chat_service=chat_service,
        identity_resolver=identity_resolver,
        group_identity_resolver=group_identity_resolver,
        playthrough_service=playthrough_service,
        telegram_runtime=telegram_runtime,
        runtime_state=RuntimeState(),
        db_health_probe=db_health_probe,
        db_startup_check_fail_fast=settings.postgres_startup_check_fail_fast,
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
        if container.db_health_probe is None:
            db_status = "n/a"
        else:
            db_status = "available" if await container.db_health_probe.ping() else "unavailable"
        return {
            "status": "ok",
            "services": {
                "llm": llm_status,
                "telegram": telegram_status,
                "db": db_status,
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
