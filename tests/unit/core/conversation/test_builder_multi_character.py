from uuid import UUID

from rp_engine.core.character.character import Character
from rp_engine.core.conversation.builder import (
    PROMPT_SECTION_CHARACTER,
    PROMPT_SECTION_METADATA_KEY,
    PROMPT_SECTION_RESPONSE_FORMAT,
    ConversationBuilder,
    ScenarioConversationInput,
)
from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition
from rp_engine.core.scenario.scenario_session import ScenarioSession
from rp_engine.core.user.user import User
from rp_engine.core.world.world import World

OWNER_ID = UUID("00000000-0000-0000-0000-000000000002")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")

INSTRUCTION = "Play every character above. Make clear in the prose who acts and who speaks."


def _character(char_id: str, name: str, **overrides: str) -> Character:
    fields = {
        "description": "{{char}} is called " + name,
        "personality": "Calm",
        "greeting": "I am {{char}}",
        **overrides,
    }
    return Character(
        id=char_id,
        name=name,
        description=fields["description"],
        personality=fields["personality"],
        greeting=fields["greeting"],
    )


def _build(
    characters: dict[str, Character],
    participants: dict[str, str],
    *,
    world: World | None = None,
    rules: list[str] | None = None,
) -> Conversation:
    scenario = ScenarioDefinition(
        id="scenario_1",
        owner_id=OWNER_ID,
        name="Test Scenario",
        description="",
        world=world,
        characters=characters,
        rules=rules or [],
    )
    session = ScenarioSession(
        id=SESSION_ID,
        scenario_definition_id="scenario_1",
        owner_kind="user",
        owner_id=OWNER_ID,
        active_participants=participants,
    )
    return ConversationBuilder().build(
        ScenarioConversationInput(
            scenario=scenario,
            session=session,
            user=User(id=OWNER_ID, display_name="Pablo"),
            memory_messages=[],
            user_message="Hello",
        )
    )


def _section(conversation: Conversation, name: str) -> str:
    return "\n\n".join(
        m.content
        for m in conversation.messages
        if m.role == ConversationRole.SYSTEM and m.metadata.get(PROMPT_SECTION_METADATA_KEY) == name
    )


def _two_characters() -> dict[str, Character]:
    return {
        "hero": _character("alice", "Alice"),
        "rival": _character("bob", "Bob"),
    }


def test_two_characters_send_both_cards_in_role_name_order() -> None:
    conversation = _build(_two_characters(), {"hero": "alice", "rival": "bob"})

    card = _section(conversation, PROMPT_SECTION_CHARACTER)
    assert card.count("[Character]") == 2
    assert card.index("[Character]\n Alice") < card.index("[Character]\n Bob")
    assert "[Greeting]\n I am Alice" in card
    assert "[Greeting]\n I am Bob" in card


def test_cards_are_sorted_by_role_name_not_by_written_order() -> None:
    conversation = _build(_two_characters(), {"rival": "bob", "hero": "alice"})

    card = _section(conversation, PROMPT_SECTION_CHARACTER)
    assert card.index("[Character]\n Alice") < card.index("[Character]\n Bob")


def test_first_card_and_char_outside_cards_follow_the_sorted_role_order() -> None:
    characters = {
        "narrator": _character("nora", "Nora"),
        "jane": _character("jane_id", "Jane"),
    }
    world = World(id="default", name="Main", description="Home of {{char}}")
    conversation = _build(characters, {"narrator": "nora", "jane": "jane_id"}, world=world)

    card = _section(conversation, PROMPT_SECTION_CHARACTER)
    assert card.index("[Character]\n Jane") < card.index("[Character]\n Nora")
    assert "Home of Jane" in _section(conversation, "world")


def test_sole_character_is_the_only_card_when_no_participant_matches() -> None:
    conversation = _build({"hero": _character("alice", "Alice")}, {"ghost": "nobody"})

    card = _section(conversation, PROMPT_SECTION_CHARACTER)
    assert card.count("[Character]") == 1
    assert "[Character]\n Alice" in card


def test_participant_is_matched_by_character_id_when_role_is_unknown() -> None:
    conversation = _build(_two_characters(), {"hero": "alice", "sidekick": "bob"})

    card = _section(conversation, PROMPT_SECTION_CHARACTER)
    assert "[Character]\n Alice" in card
    assert "[Character]\n Bob" in card


def test_participants_missing_from_the_scenario_are_skipped() -> None:
    conversation = _build(_two_characters(), {"ghost": "nobody", "rival": "bob"})

    card = _section(conversation, PROMPT_SECTION_CHARACTER)
    assert card.count("[Character]") == 1
    assert "[Character]\n Bob" in card


def test_two_characters_add_the_play_every_character_line_after_the_cards() -> None:
    conversation = _build(_two_characters(), {"hero": "alice", "rival": "bob"})

    card = _section(conversation, PROMPT_SECTION_CHARACTER)
    assert INSTRUCTION in card
    assert card.index(INSTRUCTION) > card.index("[Character]\n Bob")
    assert card.count(INSTRUCTION) == 1


def test_one_character_has_no_instruction_line() -> None:
    conversation = _build({"hero": _character("alice", "Alice")}, {"hero": "alice"})

    joined = "\n".join(m.content for m in conversation.messages)
    assert "Play every character above" not in joined


def test_one_character_prompt_is_unchanged_apart_from_the_italics_wording() -> None:
    conversation = _build({"hero": _character("alice", "Alice")}, {"hero": "alice"})

    assert _section(conversation, PROMPT_SECTION_CHARACTER) == (
        "[Character]\n Alice\n"
        "[Description]\n Alice is called Alice\n"
        "[Personality]\n Calm\n"
        "[Greeting]\n I am Alice"
    )
    assert _section(conversation, PROMPT_SECTION_RESPONSE_FORMAT) == (
        "[Response Format]\n"
        "                Write naturally. Never include labels such as "
        '"Narration", "Action", or "Dialogue".\n'
        "                Keep scene descriptions brief and only describe observable events.\n"
        "                Write the characters' physical actions in *italics*.\n"
        "                Write spoken dialogue in quotation marks.\n"
        "                Prefer dialogue and interaction over exposition.\n"
        "                Avoid long monologues.\n"
        "                React to the user's latest message before introducing new "
        "descriptions.\n"
        "                Do not narrate the user's thoughts, emotions, or intentions.\n"
        "                End naturally with an opportunity for the user to respond."
    )
    sections = [
        m.metadata[PROMPT_SECTION_METADATA_KEY]
        for m in conversation.messages
        if m.role == ConversationRole.SYSTEM
    ]
    assert sections == ["character", "response_format", "memory"]


def test_response_format_keeps_the_no_labels_rule() -> None:
    conversation = _build(_two_characters(), {"hero": "alice", "rival": "bob"})

    response_format = _section(conversation, PROMPT_SECTION_RESPONSE_FORMAT)
    assert "Never include labels" in response_format
    assert "Write the characters' physical actions in *italics*." in response_format
    assert "Write the character's physical actions" not in response_format


def test_char_inside_each_card_is_that_cards_name() -> None:
    conversation = _build(_two_characters(), {"hero": "alice", "rival": "bob"})

    card = _section(conversation, PROMPT_SECTION_CHARACTER)
    assert "[Description]\n Alice is called Alice" in card
    assert "[Description]\n Bob is called Bob" in card
    assert "[Greeting]\n I am Alice" in card
    assert "[Greeting]\n I am Bob" in card
    assert "{{char}}" not in card


def test_char_outside_the_cards_is_the_first_characters_name() -> None:
    world = World(id="default", name="Main", description="Home of {{char}}")
    conversation = _build(
        _two_characters(),
        {"rival": "bob", "hero": "alice"},
        world=world,
        rules=["{{char}} never lies"],
    )

    assert "Home of Alice" in _section(conversation, "world")
    assert "Alice never lies" in _section(conversation, "scenario_rules")
