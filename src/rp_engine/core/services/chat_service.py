import logging
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.builder import ConversationBuilder, ConversationBuilderInput
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.memory.models import ConversationIdentity
from rp_engine.core.ports import (
    CharacterStore,
    ConversationStore,
    MemoryStrategy,
    SessionStore,
    UserIdentityStore,
    WorldStore,
)
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        orchestrator: RPOrchestrator,
        conversation_store: ConversationStore,
        memory_strategy: MemoryStrategy,
        user_identity_store: UserIdentityStore,
        session_store: SessionStore,
        character_store: CharacterStore,
        world_store: WorldStore,
        generation_settings: GenerationSettings,
    ) -> None:
        self._orchestrator = orchestrator
        self._conversation_store = conversation_store
        self._memory_strategy = memory_strategy
        self._user_identity_store = user_identity_store
        self._session_store = session_store
        self._character_store = character_store
        self._world_store = world_store
        self._generation_settings = generation_settings
        self._conversation_builder = ConversationBuilder()

    async def send_message(
        self,
        *,
        conversation_identity: ConversationIdentity,
        message: str,
        user_id: str | None = None,
        username: str | None = None,
        display_name: str | None = None,
    ) -> str:
        session_id = self._require_session_identity(conversation_identity)
        memory_key = conversation_identity.to_memory_key()
        logger.info(
            "ChatService called",
            extra={"memory_key": memory_key.value, "session_id": str(session_id)},
        )
        cleaned_message = message.strip()
        if not cleaned_message:
            raise ValueError("Message must not be empty.")

        session, user, character, world = await self._load_conversation_context(
            session_id=session_id
        )
        history = await self._conversation_store.load_messages(memory_key)
        context_messages = self._memory_strategy.build_context(history)
        conversation = self._conversation_builder.build(
            ConversationBuilderInput(
                session=session,
                user=user,
                character=character,
                world=world,
                memory_messages=context_messages,
                user_message=cleaned_message,
            )
        )
        request = GenerationRequest(
            memory_key=memory_key,
            conversation=conversation,
            settings=self._generation_settings,
        )
        llm_response = await self._orchestrator.generate_reply(request)
        character_response = llm_response.content
        await self._conversation_store.save_message(
            memory_key,
            ConversationMessage(
                role=ConversationRole.USER,
                content=cleaned_message,
                metadata={
                    key: value
                    for key, value in {
                        "user_id": user_id,
                        "username": username,
                        "display_name": display_name,
                    }.items()
                    if value is not None
                },
            ),
        )
        await self._conversation_store.save_message(
            memory_key,
            ConversationMessage(role=ConversationRole.CHARACTER, content=character_response),
        )
        return character_response

    async def continue_story(
        self,
        *,
        conversation_identity: ConversationIdentity,
    ) -> str:
        session_id = self._require_session_identity(conversation_identity)
        memory_key = conversation_identity.to_memory_key()
        logger.info(
            "ChatService continue called",
            extra={"memory_key": memory_key.value, "session_id": str(session_id)},
        )
        session, user, character, world = await self._load_conversation_context(
            session_id=session_id
        )
        history = await self._conversation_store.load_messages(memory_key)
        context_messages = self._memory_strategy.build_context(history)
        conversation = self._conversation_builder.build_continue(
            ConversationBuilderInput(
                session=session,
                user=user,
                character=character,
                world=world,
                memory_messages=context_messages,
                user_message="continue",
            )
        )
        request = GenerationRequest(
            memory_key=memory_key,
            conversation=conversation,
            settings=self._generation_settings,
        )
        llm_response = await self._orchestrator.generate_reply(request)
        character_response = llm_response.content
        await self._conversation_store.save_message(
            memory_key,
            ConversationMessage(role=ConversationRole.CHARACTER, content=character_response),
        )
        return character_response

    async def clear_conversation(
        self,
        *,
        conversation_identity: ConversationIdentity,
    ) -> None:
        memory_key = conversation_identity.to_memory_key()
        logger.info("ChatService clear called", extra={"memory_key": memory_key.value})
        await self._conversation_store.clear(memory_key)

    @staticmethod
    def _require_session_identity(conversation_identity: ConversationIdentity) -> UUID:
        if conversation_identity.owner_kind != "session":
            raise ValueError("Conversation identity must be session-scoped.")
        try:
            return UUID(conversation_identity.owner_id)
        except ValueError as exc:
            raise ValueError("Conversation identity has an invalid session id.") from exc

    async def _load_conversation_context(
        self,
        *,
        session_id: UUID,
    ) -> tuple[Session, User, Character, World]:
        session = await self._session_store.get_by_id(session_id)
        if session is None:
            raise ValueError("Session not found for conversation identity.")

        user = await self._user_identity_store.get_by_id(session.user_id)
        if user is None:
            raise ValueError("User not found for session.")

        character = await self._character_store.get_by_id(session.character_id)
        if character is None:
            raise ValueError("Character not found for session.")

        world = await self._world_store.get_by_id(session.world_id)
        if world is None:
            raise ValueError("World not found for session.")

        return session, user, character, world
