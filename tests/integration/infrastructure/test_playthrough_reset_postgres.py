"""Reset tiers driven end to end against a real Postgres.

The unit-level reset tests run against a fake session store, so they can only prove the
*service* asks for the right things — a fake that filters superseded sessions correctly
will happily pass while the real SQL does not. This exercises `PlaythroughService` on top
of the actual repositories, which is where session resurrection (ADR-025 / S016) lives.
"""

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from rp_engine.application.services.playthrough_service import PlaythroughService
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.infrastructure.postgres import (
    PostgresConfig,
    PostgresConversationStore,
    PostgresScenarioDefinitionStore,
    PostgresScenarioSessionStore,
    create_engine,
    create_session_factory,
)
from rp_engine.infrastructure.scenario_transfer import SYSTEM_OWNER_ID

USER_ID = UUID("00000000-0000-0000-0000-0000000000aa")

_TRUNCATE = (
    "TRUNCATE TABLE active_scenario_sessions, scenario_sessions, scenario_definitions, "
    "conversation_messages RESTART IDENTITY CASCADE"
)


async def _prepare_engine(config: PostgresConfig) -> AsyncEngine:
    engine = create_engine(config)
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    return engine


@pytest_asyncio.fixture
async def service(postgres_config: PostgresConfig) -> AsyncIterator[PlaythroughService]:
    engine = await _prepare_engine(postgres_config)
    factory = create_session_factory(engine)
    definition_store = PostgresScenarioDefinitionStore(factory)
    await definition_store.save(
        ScenarioDefinition(
            id="vault",
            owner_id=SYSTEM_OWNER_ID,
            name="The Vault",
            description="A heist.",
            initial_context="You face the door.",
        )
    )
    yield PlaythroughService(
        scenario_definition_store=definition_store,
        scenario_session_store=PostgresScenarioSessionStore(factory),
        conversation_store=PostgresConversationStore(factory),
    )
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await engine.dispose()


def _memory_key(session_id: UUID) -> MemoryKey:
    return ConversationIdentity.for_session(str(session_id)).to_memory_key()


@pytest.mark.asyncio
async def test_replaying_a_scenario_after_a_restart_does_not_resurrect_the_old_session(
    service: PlaythroughService,
) -> None:
    first = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert first is not None

    second = await service.restart(owner_kind="user", owner_id=USER_ID)
    assert second is not None
    assert second.session.id != first.session.id

    replayed = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")

    assert replayed is not None
    assert replayed.session.id == second.session.id, "resurrected a superseded session"
    assert replayed.resumed is True


@pytest.mark.asyncio
async def test_the_pre_restart_transcript_never_comes_back(
    service: PlaythroughService,
) -> None:
    """The symptom players actually see: the *old story* reappears."""
    first = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert first is not None
    conversation_store = service._conversation_store  # noqa: SLF001 — asserting on stored state
    await conversation_store.save_message(
        _memory_key(first.session.id),
        ConversationMessage(role=ConversationRole.CHARACTER, content="THE OLD STORY."),
    )

    await service.restart(owner_kind="user", owner_id=USER_ID)
    replayed = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")

    assert replayed is not None
    assert replayed.opening == "You face the door."
    active = await service.get_active(owner_kind="user", owner_id=USER_ID)
    assert active is not None
    assert await service.resume_text(session=active) == "You face the door."


@pytest.mark.asyncio
async def test_clear_also_supersedes_and_does_not_resurrect(
    service: PlaythroughService,
) -> None:
    first = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert first is not None

    cleared = await service.clear(owner_kind="user", owner_id=USER_ID)
    assert cleared is not None

    replayed = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert replayed is not None
    assert replayed.session.id == cleared.session.id


@pytest.mark.asyncio
async def test_a_second_live_session_for_the_same_scenario_is_rejected(
    service: PlaythroughService,
) -> None:
    """The invariant `find_by_definition` has always assumed, now enforced by the database.

    Duplicate live rows are what made resurrection possible: with two of them the lookup is
    a coin flip between the current story and a retired one. A loud failure beats that.
    """
    started = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert started is not None
    store = service._scenario_session_store  # noqa: SLF001

    duplicate = ScenarioSession.create_for_user(
        scenario_definition_id="vault", user_id=USER_ID
    )
    with pytest.raises(IntegrityError):
        await store.save(duplicate)


@pytest.mark.asyncio
async def test_a_superseded_session_does_not_block_a_new_one(
    service: PlaythroughService,
) -> None:
    # Uniqueness is partial, so retiring a session frees the slot immediately.
    first = await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    assert first is not None
    second = await service.restart(owner_kind="user", owner_id=USER_ID)
    assert second is not None
    third = await service.restart(owner_kind="user", owner_id=USER_ID)
    assert third is not None
    assert len({first.session.id, second.session.id, third.session.id}) == 3


@pytest.mark.asyncio
async def test_repeated_restarts_leave_exactly_one_live_session(
    service: PlaythroughService,
) -> None:
    await service.start(owner_kind="user", owner_id=USER_ID, scenario_id="vault")
    for _ in range(3):
        assert await service.restart(owner_kind="user", owner_id=USER_ID) is not None

    store = service._scenario_session_store  # noqa: SLF001
    live = await store.find_by_owner("user", USER_ID)
    every = await store.find_by_owner("user", USER_ID, include_deleted=True)

    assert len(live) == 1
    assert len(every) == 4
