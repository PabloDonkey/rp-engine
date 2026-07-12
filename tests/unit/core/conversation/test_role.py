from rp_engine.core.conversation.role import ConversationRole


def test_conversation_role_contains_domain_roles_only() -> None:
    assert ConversationRole.SYSTEM.value == "system"
    assert ConversationRole.USER.value == "user"
    assert ConversationRole.CHARACTER.value == "character"
    assert "assistant" not in {role.value for role in ConversationRole}
