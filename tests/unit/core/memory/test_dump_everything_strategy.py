from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.memory.dump_everything_strategy import DumpEverythingStrategy


def test_dump_everything_strategy_returns_all_messages() -> None:
    strategy = DumpEverythingStrategy()
    messages = [
        ConversationMessage(role=ConversationRole.USER, content="hello"),
        ConversationMessage(role=ConversationRole.CHARACTER, content="hi"),
    ]

    context = strategy.build_context(messages)

    assert context == messages
    assert context is not messages
