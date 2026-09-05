import logging
from dataclasses import dataclass, replace
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rp_engine.adapters.api import create_admin_router, create_play_router
from rp_engine.adapters.api import create_router as create_api_router
from rp_engine.adapters.telegram.adapter import (
    TelegramAdapter,
    TelegramRuntime,
    create_telegram_application,
)
from rp_engine.adapters.telegram.authorization import TelegramAuthorization
from rp_engine.adapters.telegram.narrator_store import TelegramNarratorStore
from rp_engine.adapters.telegram.pending_persona_store import TelegramPendingPersonaStore
from rp_engine.app.lifespan import create_lifespan
from rp_engine.app.runtime_state import RuntimeState
from rp_engine.application.services.admin_service import AdminService
from rp_engine.application.services.chat_service import ChatService
from rp_engine.application.services.group_identity_resolver import GroupIdentityResolver
from rp_engine.application.services.identity_resolver import IdentityResolver
from rp_engine.application.services.playthrough_service import PlaythroughService
from rp_engine.application.services.scenario_transfer_service import ScenarioTransferService
from rp_engine.application.services.session_directive_service import SessionDirectiveService
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.memory.context_budget import ContextBudget
from rp_engine.core.memory.lorebook_source import LorebookSource
from rp_engine.core.memory.pipeline import MemoryPipeline
from rp_engine.core.memory.recent_window_source import RecentWindowSource
from rp_engine.core.memory.rolling_summary_source import RollingSummarySource
from rp_engine.core.ports import (
    ConversationStore,
    GenerationTraceStore,
    GroupIdentityStore,
    LLMProvider,
    LorebookStore,
    ScenarioDefinitionStore,
    ScenarioSessionStore,
    SessionSummaryStore,
    TokenCounter,
    UserIdentityStore,
)
from rp_engine.infrastructure.config.settings import Settings, get_settings
from rp_engine.infrastructure.llm.lmstudio import (
    LMStudioConversationSummarizer,
    LMStudioProvider,
    LMStudioTokenCounter,
)
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
    PostgresLorebookStore,
    PostgresScenarioDefinitionStore,
    PostgresScenarioSessionStore,
    PostgresSessionSummaryStore,
    PostgresUserIdentityStore,
)
from rp_engine.infrastructure.tasks import AsyncioTaskScheduler

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
    token_counter: TokenCounter
    context_budget: ContextBudget
    orchestrator: RPOrchestrator
    chat_service: ChatService
    identity_resolver: IdentityResolver
    group_identity_resolver: GroupIdentityResolver
    playthrough_service: PlaythroughService
    session_directive_service: SessionDirectiveService
    scenario_transfer_service: ScenarioTransferService
    scenario_catalog_dirs: list[str]
    admin_service: AdminService
    telegram_authorization: TelegramAuthorization
    telegram_runtime: TelegramRuntime | None
    task_scheduler: AsyncioTaskScheduler
    runtime_state: RuntimeState
    db_health_probe: PostgresHealthProbe
    db_startup_check_fail_fast: bool


def build_container(settings: Settings) -> AppContainer:
    logger.info("Environment loaded", extra={"app_environment": settings.app_environment})

    llm_provider = LMStudioProvider(
        model_name=settings.lmstudio_model,
        api_host=settings.lmstudio_api_host,
        max_tokens=settings.lmstudio_max_tokens,
        temperature=settings.lmstudio_temperature,
        reasoning_start_tag=settings.lmstudio_reasoning_start_tag,
        reasoning_end_tag=settings.lmstudio_reasoning_end_tag,
    )
    # Counting and generating share one model, so they share one model name. The counter
    # is built after the provider only because the provider is what configures the LM
    # Studio default client for the process.
    lmstudio_token_counter = LMStudioTokenCounter(
        model_name=settings.lmstudio_model,
        api_host=settings.lmstudio_api_host,
        fallback_context_length=settings.memory_fallback_context_length,
    )
    context_budget = ContextBudget(
        context_window=lmstudio_token_counter,
        share=settings.memory_context_budget_share,
    )
    postgres_config = PostgresConfig.from_settings(settings)
    postgres_engine = create_engine(postgres_config)
    postgres_session_factory = create_session_factory(postgres_engine)
    conversation_store: ConversationStore = PostgresConversationStore(postgres_session_factory)
    scenario_definition_store: ScenarioDefinitionStore = PostgresScenarioDefinitionStore(
        postgres_session_factory
    )
    scenario_session_store: ScenarioSessionStore = PostgresScenarioSessionStore(
        postgres_session_factory
    )
    generation_trace_store: GenerationTraceStore = PostgresGenerationTraceStore(
        postgres_session_factory
    )
    session_summary_store: SessionSummaryStore = PostgresSessionSummaryStore(
        postgres_session_factory
    )
    lorebook_store: LorebookStore = PostgresLorebookStore(postgres_session_factory)
    user_identity_store: UserIdentityStore = PostgresUserIdentityStore(postgres_session_factory)
    group_identity_store: GroupIdentityStore = PostgresGroupIdentityStore(postgres_session_factory)
    db_health_probe = PostgresHealthProbe(
        postgres_engine, alembic_ini_path=Path.cwd() / "alembic.ini"
    )

    identity_resolver = IdentityResolver(store=user_identity_store)
    group_identity_resolver = GroupIdentityResolver(store=group_identity_store)
    scenario_transfer_service = ScenarioTransferService(
        scenario_definition_store=scenario_definition_store,
        scenario_session_store=scenario_session_store,
        conversation_store=conversation_store,
        lorebook_store=lorebook_store,
    )
    playthrough_service = PlaythroughService(
        scenario_definition_store=scenario_definition_store,
        scenario_session_store=scenario_session_store,
        conversation_store=conversation_store,
    )
    session_directive_service = SessionDirectiveService(
        scenario_session_store=scenario_session_store,
    )
    # Built here rather than inline in the source list: the admin panel reads its status
    # and can run its pass by hand, so the panel and the pipeline must share one instance.
    rolling_summary_source = RollingSummarySource(
        summary_store=session_summary_store,
        conversation_store=conversation_store,
        summarizer=LMStudioConversationSummarizer(
            llm_provider=llm_provider,
            max_tokens=settings.memory_summary_max_tokens,
        ),
        token_counter=lmstudio_token_counter,
        model_name=settings.lmstudio_model,
        high_water_share=settings.memory_summary_high_water_share,
        min_fold_share=settings.memory_summary_min_fold_share,
    )
    # The layer list of ADR-026. Layers 03 and 04 append here as they land; nothing else
    # changes when they do.
    memory_pipeline = MemoryPipeline(
        sources=[
            RecentWindowSource(token_counter=lmstudio_token_counter),
            rolling_summary_source,
            LorebookSource(store=lorebook_store, token_counter=lmstudio_token_counter),
        ],
        context_budget=context_budget,
    )
    # The write half of every memory layer runs here, off the turn path (ADR-026 decision
    # 1). `app/lifespan.py` starts and cancels it next to the Telegram runtime, which is
    # why the container holds the concrete type rather than the port.
    task_scheduler = AsyncioTaskScheduler()
    generation_settings = GenerationSettings(
        temperature=settings.lmstudio_temperature,
        max_tokens=settings.lmstudio_max_tokens,
        top_p=settings.lmstudio_top_p_sampling,
    )
    # Same sampling, bigger budget: the retry only exists because the cap was the constraint.
    length_retry_settings = replace(
        generation_settings,
        max_tokens=settings.lmstudio_length_retry_max_tokens,
    )
    admin_service = AdminService(
        user_identity_store=user_identity_store,
        scenario_session_store=scenario_session_store,
        conversation_store=conversation_store,
        generation_trace_store=generation_trace_store,
        scenario_definition_store=scenario_definition_store,
        session_summary_store=session_summary_store,
        rolling_summary_source=rolling_summary_source,
        context_budget=context_budget,
        lorebook_store=lorebook_store,
    )
    telegram_authorization = TelegramAuthorization.from_directory(
        settings.telegram_authorization_dir,
        admin_user_id=settings.telegram_admin_user_id,
    )

    logger.info("LM Studio provider initialized", extra={"api_host": settings.lmstudio_api_host})
    orchestrator = RPOrchestrator(llm_provider=llm_provider)
    chat_service = ChatService(
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        memory_pipeline=memory_pipeline,
        token_counter=lmstudio_token_counter,
        user_identity_store=user_identity_store,
        group_identity_store=group_identity_store,
        scenario_session_store=scenario_session_store,
        scenario_definition_store=scenario_definition_store,
        generation_settings=generation_settings,
        generation_trace_store=generation_trace_store,
        generation_trace_mode=settings.debug_generation_trace,
        length_retry_settings=length_retry_settings,
        task_scheduler=task_scheduler,
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
            session_directive_service=session_directive_service,
            authorization=telegram_authorization,
            admin_telegram_user_id=settings.telegram_admin_user_id,
            unauthorized_message=settings.telegram_unauthorized_message,
            message_max_length=settings.telegram_message_max_length,
            narrator_store=TelegramNarratorStore(),
            pending_persona_store=TelegramPendingPersonaStore(),
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
        token_counter=lmstudio_token_counter,
        context_budget=context_budget,
        orchestrator=orchestrator,
        chat_service=chat_service,
        identity_resolver=identity_resolver,
        group_identity_resolver=group_identity_resolver,
        playthrough_service=playthrough_service,
        session_directive_service=session_directive_service,
        scenario_transfer_service=scenario_transfer_service,
        scenario_catalog_dirs=settings.scenario_catalog_dirs,
        admin_service=admin_service,
        telegram_authorization=telegram_authorization,
        telegram_runtime=telegram_runtime,
        task_scheduler=task_scheduler,
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
    # Admin panel has no auth (trust the Tailscale network, see docs/adr/); allow the
    # Vue dev server / any tailnet origin to call it rather than fighting CORS in that model.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_api_router(container.chat_service))
    app.include_router(
        create_admin_router(
            container.admin_service,
            container.telegram_authorization,
            container.scenario_transfer_service,
        )
    )
    app.include_router(create_play_router(container.admin_service, container.chat_service))

    @app.get("/health")
    async def health() -> dict[str, object]:
        llm_status = "available" if container.settings.lmstudio_model else "unavailable"
        telegram_status = "running" if container.telegram_runtime is not None else "disabled"
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
