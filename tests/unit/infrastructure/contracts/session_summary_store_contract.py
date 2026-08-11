from uuid import UUID

from rp_engine.core.memory.session_summary import SessionSummary
from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.ports.session_summary_store import SessionSummaryStore
from rp_engine.core.scenario.scenario_session import ScenarioSession

USER_ID = UUID("00000000-0000-0000-0000-000000000030")


async def assert_session_summary_store_contract(
    store: SessionSummaryStore,
    *,
    session_store: ScenarioSessionStore,
) -> None:
    """Layer 01 keeps one recap per session, rewritten in place.

    A session has to exist first: the recap is a claim about a story, so the schema points
    it at the story it describes.
    """
    session = await session_store.save(
        ScenarioSession.create_for_user(scenario_definition_id="def-1", user_id=USER_ID)
    )

    assert await store.get(session.id) is None

    first = SessionSummary.create(
        session_id=session.id,
        summary="They crossed the river and lost the map.",
        covers_through_turn=7,
        tokens=9,
        model_name="model-a",
    )
    assert await store.save(first) == first

    loaded = await store.get(session.id)
    assert loaded == first

    # A later pass rewrites the row rather than adding one.
    second = first.rewritten(
        summary="They crossed the river, lost the map, and met the ferryman.",
        covers_through_turn=12,
        tokens=13,
        model_name="model-b",
    )
    await store.save(second)

    reloaded = await store.get(session.id)
    assert reloaded is not None
    assert reloaded.summary == second.summary
    assert reloaded.covers_through_turn == 12
    assert reloaded.tokens == 13
    assert reloaded.model_name == "model-b"
    # The recap keeps the moment it first existed; only `updated_at` moves.
    assert reloaded.created_at == first.created_at
    assert reloaded.updated_at >= first.updated_at

    # Recaps are scoped to their own session.
    other = await session_store.save(
        ScenarioSession.create_for_user(scenario_definition_id="def-2", user_id=USER_ID)
    )
    assert await store.get(other.id) is None
