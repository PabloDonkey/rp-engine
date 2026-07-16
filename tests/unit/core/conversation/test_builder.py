from datetime import UTC, datetime
from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.builder import ConversationBuilder, ConversationBuilderInput
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.session.session import Session
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World


def test_builder_resolves_templates_and_orders_messages() -> None:
    builder = ConversationBuilder()
    session = Session(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        owner_kind="user",
        owner_id=UUID("00000000-0000-0000-0000-000000000002"),
        character_id="belzebuth",
        world_id="default",
        created_at=datetime.now(UTC),
    )
    user = User(id=session.owner_id, display_name="Pablo")
    character = Character(
        id="belzebuth",
        name="Belzebuth",
        description="{{char}} likes {{user}}",
        personality="Bold",
        greeting="Hello {{user}}",
    )
    world = World(
        id="default",
        name="Main",
        description="{{user}} travels with {{char}}",
    )

    memory = [
        ConversationMessage(role=ConversationRole.CHARACTER, content="Welcome back, {{user}}."),
    ]

    conversation = builder.build(
        ConversationBuilderInput(
            session=session,
            user=user,
            character=character,
            world=world,
            memory_messages=memory,
            user_message="Hello {{char}}.",
        )
    )

    assert len(conversation.messages) == 6
    assert [message.role for message in conversation.messages[:4]] == [
        ConversationRole.SYSTEM,
        ConversationRole.SYSTEM,
        ConversationRole.SYSTEM,
        ConversationRole.SYSTEM,
    ]
    assert conversation.messages[4] == ConversationMessage(
        role=ConversationRole.CHARACTER,
        content="Welcome back, Pablo.",
        metadata={},
    )
    assert conversation.messages[5] == ConversationMessage(
        role=ConversationRole.USER,
        content="Hello Belzebuth.",
        metadata={},
    )

    joined_content = "\n".join(message.content for message in conversation.messages)
    assert "{{char}}" not in joined_content
    assert "{{user}}" not in joined_content
