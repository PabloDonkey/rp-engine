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

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlaythroughStart:
    session: ScenarioSession
    scenario: ScenarioDefinition
    opening: str
    resumed: bool = False


class PlaythroughService:
    """Coordinates scenario playthroughs: listing, starting, resuming and restarting.

    A playthrough is a `ScenarioSession` bound to a curated `ScenarioDefinition` from
    `ScenarioDefinitionStore` (Postgres is the sole source of truth, see ADR-024). Starting
    one seeds the scenario's opening narration into the conversation so the player
    immediately sees where they are.
    """

    def __init__(
        self,
        *,
        scenario_definition_store: ScenarioDefinitionStore,
        scenario_session_store: ScenarioSessionStore,
        conversation_store: ConversationStore,
    ) -> None:
        self._scenario_definition_store = scenario_definition_store
        self._scenario_session_store = scenario_session_store
        self._conversation_store = conversation_store

    async def list_scenarios(
        self, *, caller_group_chat_id: str | None = None
    ) -> list[ScenarioDefinition]:
        """Scenarios the caller may browse.

        `caller_group_chat_id` is the Telegram chat id for group callers (None for
        direct chats). UNLISTED scenarios are always excluded; RESTRICTED ones appear
        only for the groups they are locked to.
        """
        scenarios = await self._scenario_definition_store.list_all()
        return sorted(
            (s for s in scenarios if s.is_listed_for(caller_group_chat_id)),
            key=lambda scenario: scenario.name.lower(),
        )

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
        caller_group_chat_id: str | None = None,
    ) -> PlaythroughStart | None:
        scenario = await self._scenario_definition_store.get_by_id(scenario_id)
        # A caller who may not access a RESTRICTED scenario is treated as if it does not
        # exist, so locking never leaks the id through a distinct error.
        if scenario is None or not scenario.is_playable_by(caller_group_chat_id):
            return None
        existing = await self._scenario_session_store.find_by_definition(
            owner_kind=owner_kind,
            owner_id=owner_id,
            scenario_definition_id=scenario.id,
        )
        if existing is not None:
            return await self._resume(
                owner_kind=owner_kind, owner_id=owner_id, session=existing, scenario=scenario
            )
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
        scenario = await self._scenario_definition_store.get_by_id(active.scenario_definition_id)
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

    async def _resume(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        session: ScenarioSession,
        scenario: ScenarioDefinition,
    ) -> PlaythroughStart:
        # An owner already has a session for this scenario — reactivate it rather than
        # starting a fresh one, which would orphan the existing conversation history.
        await self._scenario_session_store.set_active_for_owner(
            owner_kind=owner_kind,
            owner_id=owner_id,
            session_id=session.id,
        )
        resume = await self.resume_text(session=session)
        return PlaythroughStart(
            session=session,
            scenario=scenario,
            opening=resume or self._opening_text(scenario),
            resumed=True,
        )

    async def _begin(
        self,
        *,
        owner_kind: SessionOwnerKind,
        owner_id: UUID,
        scenario: ScenarioDefinition,
    ) -> PlaythroughStart:
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
