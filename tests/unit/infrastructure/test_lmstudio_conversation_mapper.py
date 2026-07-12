import pytest

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.infrastructure.llm.lmstudio.conversation_mapper import LMStudioConversationMapper


class FakeChat:
    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.user_messages: list[str] = []
        self.assistant_messages: list[str] = []

    def add_user_message(self, message: str) -> None:
        self.user_messages.append(message)

    def add_assistant_message(self, message: str) -> None:
        self.assistant_messages.append(message)


def test_mapper_maps_character_role_to_assistant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.conversation_mapper.lms.Chat",
        FakeChat,
    )

    conversation = Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="system context"),
            ConversationMessage(role=ConversationRole.USER, content="hello"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="hi there"),
        ]
    )

    mapped = LMStudioConversationMapper().map_conversation(conversation)

    assert mapped.system_prompt == "system context"
    assert mapped.user_messages == ["hello"]
    assert mapped.assistant_messages == ["hi there"]
