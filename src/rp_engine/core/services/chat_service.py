import logging

from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.memory.models import ConversationIdentity, ConversationMessage
from rp_engine.core.ports import ConversationStore, MemoryStrategy

logger = logging.getLogger(__name__)

CONTINUE_INSTRUCTION = "Continue the narration naturally from the current context."


class ChatService:
    def __init__(
        self,
        orchestrator: RPOrchestrator,
        conversation_store: ConversationStore,
        memory_strategy: MemoryStrategy,
    ) -> None:
        self._orchestrator = orchestrator
        self._conversation_store = conversation_store
        self._memory_strategy = memory_strategy

    async def send_message(
        self,
        *,
        conversation_identity: ConversationIdentity,
        message: str,
    ) -> str:
        memory_key = conversation_identity.to_memory_key()
        logger.info("ChatService called", extra={"memory_key": memory_key.value})
        cleaned_message = message.strip()
        if not cleaned_message:
            raise ValueError("Message must not be empty.")

        history = await self._conversation_store.load_messages(memory_key)
        context_messages = self._memory_strategy.build_context(history)
        request = GenerationRequest(
            memory_key=memory_key,
            context_messages=context_messages,
            instruction=cleaned_message,
        )
        assistant_response = await self._orchestrator.generate_reply(request)
        await self._conversation_store.save_message(
            memory_key,
            ConversationMessage(role="user", content=cleaned_message),
        )
        await self._conversation_store.save_message(
            memory_key,
            ConversationMessage(role="assistant", content=assistant_response),
        )
        return assistant_response

    async def continue_story(
        self,
        *,
        conversation_identity: ConversationIdentity,
    ) -> str:
        memory_key = conversation_identity.to_memory_key()
        logger.info("ChatService continue called", extra={"memory_key": memory_key.value})
        history = await self._conversation_store.load_messages(memory_key)
        context_messages = self._memory_strategy.build_context(history)
        request = GenerationRequest(
            memory_key=memory_key,
            context_messages=context_messages,
            instruction=CONTINUE_INSTRUCTION,
        )
        assistant_response = await self._orchestrator.generate_reply(request)
        await self._conversation_store.save_message(
            memory_key,
            ConversationMessage(role="assistant", content=assistant_response),
        )
        return assistant_response

    async def clear_conversation(
        self,
        *,
        conversation_identity: ConversationIdentity,
    ) -> None:
        memory_key = conversation_identity.to_memory_key()
        logger.info("ChatService clear called", extra={"memory_key": memory_key.value})
        await self._conversation_store.clear(memory_key)
