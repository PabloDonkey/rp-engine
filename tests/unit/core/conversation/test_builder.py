from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.character.visibility import CharacterVisibility
from rp_engine.core.conversation.builder import ConversationBuilder, ScenarioConversationInput
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

OWNER_ID = UUID("00000000-0000-0000-0000-000000000002")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")


def _character(**overrides: object) -> Character:
    defaults: dict[str, object] = dict(
        id="belzebuth",
        owner_id=OWNER_ID,
        visibility=CharacterVisibility.PRIVATE,
        name="Belzebuth",
        description="{{char}} likes {{user}}",
        personality="Bold",
        greeting="Hello {{user}}",
    )
    defaults.update(overrides)
    return Character(**defaults)  # type: ignore[arg-type]


def _scenario(
    *,
    characters: dict[str, Character] | None = None,
    world: World | None = None,
    rules: list[str] | None = None,
    description: str = "",
    initial_context: str = "",
) -> ScenarioDefinition:
    return ScenarioDefinition(
        id="scenario_1",
        owner_id=OWNER_ID,
        name="Test Scenario",
        description=description,
        world=world,
        characters=characters or {},
        rules=rules or [],
        initial_context=initial_context,
    )


def _session(
    *,
    active_participants: dict[str, str] | None = None,
    metadata: dict[str, str] | None = None,
) -> ScenarioSession:
    return ScenarioSession(
        id=SESSION_ID,
        scenario_definition_id="scenario_1",
        owner_kind="user",
        owner_id=OWNER_ID,
        active_participants=active_participants or {},
        metadata=metadata or {},
    )


def test_builder_resolves_templates_and_orders_messages() -> None:
    builder = ConversationBuilder()
    character = _character()
    world = World(id="default", name="Main", description="{{user}} travels with {{char}}")
    scenario = _scenario(characters={"protagonist": character}, world=world)
    session = _session(active_participants={"protagonist": "belzebuth"})
    user = User(id=OWNER_ID, display_name="Pablo")
    memory = [
        ConversationMessage(role=ConversationRole.CHARACTER, content="Welcome back, {{user}}."),
    ]

    conversation = builder.build(
        ScenarioConversationInput(
            scenario=scenario,
            session=session,
            user=user,
            memory_messages=memory,
            user_message="Hello {{char}}.",
        )
    )

    # 4 system messages (character, world, rules, memory hint) + history + user turn.
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
    assert conversation.metadata == {"session_id": str(SESSION_ID)}

    joined_content = "\n".join(message.content for message in conversation.messages)
    assert "{{char}}" not in joined_content
    assert "{{user}}" not in joined_content


def test_builder_resolves_active_character_from_single_definition() -> None:
    # No explicit participant mapping; a sole character is used automatically.
    builder = ConversationBuilder()
    character = _character()
    scenario = _scenario(characters={"protagonist": character})
    session = _session()
    user = User(id=OWNER_ID, display_name="Pablo")

    conversation = builder.build(
        ScenarioConversationInput(
            scenario=scenario,
            session=session,
            user=user,
            memory_messages=[],
            user_message="Hi {{char}}.",
        )
    )

    assert conversation.messages[-1].content == "Hi Belzebuth."


def test_builder_supports_characterless_scenario() -> None:
    builder = ConversationBuilder()
    world = World(id="default", name="Main", description="A quiet place")
    scenario = _scenario(world=world)
    session = _session()
    user = User(id=OWNER_ID, display_name="Pablo")

    conversation = builder.build(
        ScenarioConversationInput(
            scenario=scenario,
            session=session,
            user=user,
            memory_messages=[],
            user_message="Describe the place.",
        )
    )

    system_messages = [
        message.content
        for message in conversation.messages
        if message.role == ConversationRole.SYSTEM
    ]
    # No [Character] block when the scenario has no characters.
    assert not any("[Character]" in message for message in system_messages)
    assert any("[World]" in message for message in system_messages)


def test_builder_includes_world_template_and_scenario_rules() -> None:
    builder = ConversationBuilder()
    character = _character(description="A knight", greeting="Hi")
    world = World(id="w", name="Eldoria", description="Realm")
    scenario = _scenario(
        characters={"protagonist": character},
        world=world,
        rules=["Never mention the modern world."],
    )
    session = _session(active_participants={"protagonist": "belzebuth"})
    user = User(id=OWNER_ID, display_name="Pablo")

    conversation = builder.build(
        ScenarioConversationInput(
            scenario=scenario,
            session=session,
            user=user,
            memory_messages=[
                ConversationMessage(role=ConversationRole.USER, content="Where am I in {{world}}?")
            ],
            user_message="Continue.",
        )
    )

    all_content = "\n".join(message.content for message in conversation.messages)
    assert "in Eldoria?" in all_content
    assert "[Scenario Rules]" in all_content
    assert "Never mention the modern world." in all_content


def test_builder_emits_scenario_intro_when_context_present() -> None:
    builder = ConversationBuilder()
    character = _character(description="A knight", greeting="Hi")
    scenario = _scenario(
        characters={"protagonist": character},
        description="A heist gone wrong.",
        initial_context="The vault door is already open.",
    )
    session = _session(active_participants={"protagonist": "belzebuth"})
    user = User(id=OWNER_ID, display_name="Pablo")

    conversation = builder.build(
        ScenarioConversationInput(
            scenario=scenario,
            session=session,
            user=user,
            memory_messages=[],
            user_message="Go.",
        )
    )

    system_messages = [
        message.content
        for message in conversation.messages
        if message.role == ConversationRole.SYSTEM
    ]
    assert any("[Initial Context]" in message for message in system_messages)
    assert any("vault door is already open" in message for message in system_messages)


def test_build_continue_uses_continue_prompt() -> None:
    builder = ConversationBuilder()
    character = _character(description="A knight", greeting="Hi")
    scenario = _scenario(characters={"protagonist": character})
    session = _session(active_participants={"protagonist": "belzebuth"})
    user = User(id=OWNER_ID, display_name="Pablo")

    conversation = builder.build_continue(
        ScenarioConversationInput(
            scenario=scenario,
            session=session,
            user=user,
            memory_messages=[],
            user_message="ignored",
        )
    )

    last = conversation.messages[-1]
    assert last.role == ConversationRole.USER
    assert last.metadata == {"source": "continue_command"}
    assert "Continue the narration" in last.content


def test_builder_includes_switch_summary_context_when_present() -> None:
    builder = ConversationBuilder()
    character = _character(description="Ancient dragon mage", greeting="Hello")
    scenario = _scenario(characters={"protagonist": character})
    session = _session(
        active_participants={"protagonist": "belzebuth"},
        metadata={
            "switch_context_to_character_id": "belzebuth",
            "switch_context_summary": (
                "The user found a hidden lab and wants to proceed carefully."
            ),
        },
    )
    user = User(id=OWNER_ID, display_name="Pablo")

    conversation = builder.build(
        ScenarioConversationInput(
            scenario=scenario,
            session=session,
            user=user,
            memory_messages=[],
            user_message="Continue.",
        )
    )

    system_messages = [
        message.content
        for message in conversation.messages
        if message.role == ConversationRole.SYSTEM
    ]
    assert any(
        "Additional context from the previous character interaction:" in message
        for message in system_messages
    )
    assert any("hidden lab" in message for message in system_messages)
