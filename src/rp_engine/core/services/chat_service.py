import logging

from rp_engine.core.engine.models import GenerationRequest
from rp_engine.core.engine.orchestrator import RPOrchestrator
from rp_engine.core.memory.models import ConversationIdentity, ConversationMessage
from rp_engine.core.ports import ConversationStore, MemoryStrategy

logger = logging.getLogger(__name__)

CONTINUE_COMMAND = "/continue"
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

    async def handle_user_message(
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

        if self._is_continue_command(cleaned_message):
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

    @staticmethod
    def _is_continue_command(message: str) -> bool:
        first_token = message.split(maxsplit=1)[0].lower()
        command = first_token.split("@", maxsplit=1)[0]
        return command == CONTINUE_COMMAND
