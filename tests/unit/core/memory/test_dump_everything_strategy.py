from rp_engine.core.memory.dump_everything_strategy import DumpEverythingStrategy
from rp_engine.core.memory.models import ConversationMessage


def test_dump_everything_strategy_returns_all_messages() -> None:
    strategy = DumpEverythingStrategy()
    messages = [
        ConversationMessage(role="user", content="hello"),
        ConversationMessage(role="assistant", content="hi"),
    ]

    context = strategy.build_context(messages)

    assert context == messages
    assert context is not messages
