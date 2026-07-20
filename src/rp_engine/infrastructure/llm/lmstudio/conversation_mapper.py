from typing import Any

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
            self._add_assistant_message(chat=chat, content=message.content)

        return chat

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

    @staticmethod
    def _add_assistant_message(*, chat: Any, content: str) -> None:
        add_assistant = getattr(chat, "add_assistant_message", None)
        if callable(add_assistant):
            add_assistant(content)
            return

        add_user = getattr(chat, "add_user_message", None)
        if callable(add_user):
            add_user(f"{content}")
            return

        raise TypeError("LM Studio chat object does not support adding messages.")
