import logging
from dataclasses import dataclass
from uuid import UUID

from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.models import ConversationIdentity, MemoryKey
from rp_engine.core.ports.conversation_store import ConversationStore
from rp_engine.core.ports.scenario_definition_store import ScenarioDefinitionStore
from rp_engine.core.ports.scenario_session_store import ScenarioSessionStore
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession, SessionOwnerKind
from rp_engine.infrastructure.catalog.scenario_catalog import ScenarioCatalog

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlaythroughStart:
    session: ScenarioSession
    scenario: ScenarioDefinition
    opening: str


class PlaythroughService:
    """Coordinates scenario playthroughs: listing, starting, resuming and restarting.

    A playthrough is a `ScenarioSession` bound to a curated `ScenarioDefinition` from the
    catalog. Starting one seeds the scenario's opening narration into the conversation so
    the player immediately sees where they are.
    """

    def __init__(
        self,
        *,
        catalog: ScenarioCatalog,
        scenario_definition_store: ScenarioDefinitionStore,
        scenario_session_store: ScenarioSessionStore,
        conversation_store: ConversationStore,
    ) -> None:
        self._catalog = catalog
        self._scenario_definition_store = scenario_definition_store
        self._scenario_session_store = scenario_session_store
        self._conversation_store = conversation_store

    def list_scenarios(self) -> list[ScenarioDefinition]:
        return self._catalog.list()

    async def get_active(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
    ) -> ScenarioSession | None:
        return await self._scenario_session_store.get_active_for_owner(
            owner_kind=owner_kind,
            owner_id=owner_id,
        )

    async def start(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        scenario_id: str,
    ) -> PlaythroughStart | None:
        scenario = self._catalog.get(scenario_id)
        if scenario is None:
            return None
        return await self._begin(owner_kind=owner_kind, owner_id=owner_id, scenario=scenario)

    async def restart(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
    ) -> PlaythroughStart | None:
        active = await self.get_active(owner_kind=owner_kind, owner_id=owner_id)
        if active is None:
            return None
        scenario = self._catalog.get(active.scenario_definition_id)
        if scenario is None:
            scenario = await self._scenario_definition_store.get_by_id(
                active.scenario_definition_id
            )
        if scenario is None:
            return None

        # Wipe the current playthrough's history before beginning again.
        await self._conversation_store.clear(self._memory_key(active.id))
        return await self._begin(owner_kind=owner_kind, owner_id=owner_id, scenario=scenario)

    async def resume_text(self, *, session: ScenarioSession) -> str | None:
        """Latest narrator line for a session, used to auto-resume from `/start`."""
        history = await self._conversation_store.load_messages(self._memory_key(session.id))
        for message in reversed(history):
            if message.role == ConversationRole.CHARACTER and message.content.strip():
                return message.content
        return None

    async def _begin(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        scenario: ScenarioDefinition,
    ) -> PlaythroughStart:
        # Persist the curated blueprint so ChatService can load it by id at reply time.
        await self._scenario_definition_store.save(scenario)

        participants = {
            role: character.id for role, character in scenario.characters.items()
        }
        if owner_kind == "user":
            session = ScenarioSession.create_for_user(
                scenario_definition_id=scenario.id,
                user_id=owner_id,
                active_participants=participants,
            )
        else:
            session = ScenarioSession.create_for_group(
                scenario_definition_id=scenario.id,
                group_id=owner_id,
                active_participants=participants,
            )
        saved = await self._scenario_session_store.save(session)
        await self._scenario_session_store.set_active_for_owner(
            owner_kind=owner_kind,
            owner_id=owner_id,
            session_id=saved.id,
        )

        opening = self._opening_text(scenario)
        memory_key = self._memory_key(saved.id)
        await self._conversation_store.clear(memory_key)
        if opening:
            await self._conversation_store.save_message(
                memory_key,
                ConversationMessage(role=ConversationRole.CHARACTER, content=opening),
            )
        return PlaythroughStart(session=saved, scenario=scenario, opening=opening)

    @staticmethod
    def _opening_text(scenario: ScenarioDefinition) -> str:
        if scenario.initial_context.strip():
            return scenario.initial_context.strip()
        for character in scenario.characters.values():
            if character.greeting.strip():
                return character.greeting.strip()
        return "Your adventure begins."

    @staticmethod
    def _memory_key(session_id: UUID) -> MemoryKey:
        return ConversationIdentity.for_session(str(session_id)).to_memory_key()
