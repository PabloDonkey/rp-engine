from rp_engine.core.memory.models import ConversationIdentity, MemoryKey


def test_conversation_identity_for_session_uses_session_prefix() -> None:
    identity = ConversationIdentity.for_session("session-123")

    assert identity.to_memory_key() == MemoryKey("session_session-123")
