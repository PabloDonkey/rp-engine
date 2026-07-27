import lmstudio as lms

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole


class LMStudioConversationMapper:
    def map_conversation(self, conversation: Conversation) -> lms.Chat:
        system_prompt = self._build_system_prompt(conversation.messages)
        chat = lms.Chat(system_prompt)

        for message in conversation.messages:
            if message.role == ConversationRole.SYSTEM:
                continue
            if message.role == ConversationRole.USER:
                chat.add_user_message(message.content)
                continue
            # `add_assistant_response` is the SDK's name. This used to probe for
            # `add_assistant_message` — which `lms.Chat` has never had — and fall back to
            # `add_user_message`, so every narrator reply was sent to the model as if the
            # player had written it. Bind the real method directly: an AttributeError on an
            # SDK upgrade is far better than silently downgrading the role again.
            chat.add_assistant_response(message.content)

        return chat

    @staticmethod
    def is_prefill(conversation: Conversation) -> bool:
        """Whether this conversation should continue its final assistant message.

        Only true when the flag is set *and* the last message really is an assistant turn —
        prefilling requires something to prefill from, and a mismatch would otherwise send a
        user message as the continuation prefix.
        """
        if not conversation.continue_final_message:
            return False
        tail = [
            message
            for message in conversation.messages
            if message.role != ConversationRole.SYSTEM
        ]
        return bool(tail) and tail[-1].role == ConversationRole.CHARACTER

    @staticmethod
    def _build_system_prompt(messages: list[ConversationMessage]) -> str:
        system_parts = [
            message.content.strip()
            for message in messages
            if message.role == ConversationRole.SYSTEM and message.content.strip()
        ]
        if not system_parts:
            return "You are a roleplay character."
        return "\n\n".join(system_parts)
