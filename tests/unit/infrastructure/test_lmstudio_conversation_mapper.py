import pytest

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.infrastructure.llm.lmstudio.conversation_mapper import LMStudioConversationMapper


class FakeChat:
    """Mirrors `lms.Chat`'s real surface.

    Deliberately does **not** define `add_assistant_message`: the SDK has no such method, and
    the previous double did — which let the mapper's `getattr` fallback route every narrator
    reply through `add_user_message` in production while this test stayed green. The double
    now records roles in order so the assertion is about what the model actually receives.
    """

    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.entries: list[tuple[str, str]] = []

    def add_user_message(self, message: str) -> None:
        self.entries.append(("user", message))

    def add_assistant_response(self, message: str) -> None:
        # The real SDK rejects this outright; a double that allows it let a live crash
        # through once already. Mirror the constraint so it cannot happen again.
        if self.entries and self.entries[-1][0] == "assistant":
            raise RuntimeError(
                "Multi-part or consecutive assistant responses are not supported."
            )
        self.entries.append(("assistant", message))


@pytest.fixture
def fake_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.conversation_mapper.lms.Chat",
        FakeChat,
    )


@pytest.mark.usefixtures("fake_chat")
def test_mapper_maps_character_role_to_assistant() -> None:
    conversation = Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="system context"),
            ConversationMessage(role=ConversationRole.USER, content="hello"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="hi there"),
        ]
    )

    mapped = LMStudioConversationMapper().map_conversation(conversation)

    assert mapped.system_prompt == "system context"
    assert mapped.entries == [("user", "hello"), ("assistant", "hi there")]


@pytest.mark.usefixtures("fake_chat")
def test_multi_turn_history_alternates_roles() -> None:
    """The regression that mattered: the model must see its own prior replies as its own,
    not as more player input."""
    conversation = Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="sys"),
            ConversationMessage(role=ConversationRole.USER, content="u1"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="a1"),
            ConversationMessage(role=ConversationRole.USER, content="u2"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="a2"),
        ]
    )

    mapped = LMStudioConversationMapper().map_conversation(conversation)

    assert [role for role, _ in mapped.entries] == ["user", "assistant", "user", "assistant"]
    assert [content for _, content in mapped.entries] == ["u1", "a1", "u2", "a2"]


@pytest.mark.usefixtures("fake_chat")
def test_system_messages_are_merged_into_the_system_prompt() -> None:
    conversation = Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="first"),
            ConversationMessage(role=ConversationRole.SYSTEM, content="second"),
            ConversationMessage(role=ConversationRole.USER, content="hello"),
        ]
    )

    mapped = LMStudioConversationMapper().map_conversation(conversation)

    assert mapped.system_prompt == "first\n\nsecond"
    assert mapped.entries == [("user", "hello")]


def test_mapper_uses_the_method_the_sdk_actually_exposes() -> None:
    """Drift guard for the whole class of bug: bind to real SDK names, do not probe."""
    import lmstudio as lms

    chat = lms.Chat("sys")
    assert hasattr(chat, "add_assistant_response")
    assert not hasattr(chat, "add_assistant_message")


@pytest.mark.usefixtures("fake_chat")
def test_resume_conversation_maps_to_an_assistant_final_chat() -> None:
    """The whole point of S018: LM Studio continues an assistant-final chat in place. No
    special mapper call is needed — mapping CHARACTER to `add_assistant_response` already
    produces the prefill shape, so this asserts the shape rather than a code path."""
    conversation = Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="sys"),
            ConversationMessage(role=ConversationRole.USER, content="go on"),
            ConversationMessage(
                role=ConversationRole.CHARACTER, content="She reached for the door and"
            ),
        ],
        continue_final_message=True,
    )

    mapped = LMStudioConversationMapper().map_conversation(conversation)

    assert mapped.entries[-1] == ("assistant", "She reached for the door and")


def test_is_prefill_requires_an_assistant_final_conversation() -> None:
    """Guards the case that silently breaks prefill: the flag set, but a memory strategy has
    trimmed or reordered so the truncated reply is no longer last."""
    mapper = LMStudioConversationMapper()
    system = ConversationMessage(role=ConversationRole.SYSTEM, content="sys")
    user = ConversationMessage(role=ConversationRole.USER, content="go on")
    character = ConversationMessage(role=ConversationRole.CHARACTER, content="partial")

    assert mapper.is_prefill(
        Conversation(messages=[system, user, character], continue_final_message=True)
    )
    # Flag set but user-final — cannot prefill.
    assert not mapper.is_prefill(
        Conversation(messages=[system, character, user], continue_final_message=True)
    )
    # Assistant-final but not a resume — a normal completed turn.
    assert not mapper.is_prefill(Conversation(messages=[system, user, character]))
    # Nothing to prefill from.
    assert not mapper.is_prefill(Conversation(messages=[system], continue_final_message=True))


@pytest.mark.usefixtures("fake_chat")
def test_consecutive_narrator_turns_are_merged_into_one_assistant_message() -> None:
    """`lms.Chat` rejects consecutive assistant responses outright, but consecutive narrator
    turns are ordinary: `/continue` advances with no player turn between. Regression for the
    live crash `Multi-part or consecutive assistant responses are not supported`."""
    conversation = Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="sys"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="The opening."),
            ConversationMessage(role=ConversationRole.USER, content="I look around."),
            ConversationMessage(role=ConversationRole.CHARACTER, content="A door creaks."),
            ConversationMessage(role=ConversationRole.CHARACTER, content="Someone enters."),
        ]
    )

    mapped = LMStudioConversationMapper().map_conversation(conversation)

    assert mapped.entries == [
        ("assistant", "The opening."),
        ("user", "I look around."),
        ("assistant", "A door creaks.\n\nSomeone enters."),
    ]


@pytest.mark.usefixtures("fake_chat")
def test_a_truncated_turn_is_rejoined_without_a_paragraph_break() -> None:
    """A resumed continuation is the rest of the sentence, not a new beat."""
    conversation = Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="sys"),
            ConversationMessage(role=ConversationRole.USER, content="go on"),
            ConversationMessage(
                role=ConversationRole.CHARACTER,
                content="A door creaks open and behind it",
                metadata={"finish_reason": "length"},
            ),
            ConversationMessage(
                role=ConversationRole.CHARACTER,
                content=" stands a figure.",
                metadata={"finish_reason": "stop"},
            ),
        ]
    )

    mapped = LMStudioConversationMapper().map_conversation(conversation)

    assert mapped.entries[-1] == (
        "assistant",
        "A door creaks open and behind it stands a figure.",
    )


@pytest.mark.usefixtures("fake_chat")
def test_merging_preserves_the_prefill_shape_for_a_resume() -> None:
    """The merged run must still end with the truncated text, so the prefill continues from
    the right tokens."""
    conversation = Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="sys"),
            ConversationMessage(role=ConversationRole.USER, content="go on"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="A first beat."),
            ConversationMessage(
                role=ConversationRole.CHARACTER,
                content="She reached for the door and",
                metadata={"finish_reason": "length"},
            ),
        ],
        continue_final_message=True,
    )

    mapper = LMStudioConversationMapper()
    mapped = mapper.map_conversation(conversation)

    assert mapper.is_prefill(conversation)
    assert mapped.entries[-1] == (
        "assistant",
        "A first beat.\n\nShe reached for the door and",
    )


@pytest.mark.usefixtures("fake_chat")
def test_a_run_of_three_narrator_turns_collapses_to_one_entry() -> None:
    conversation = Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="sys"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="one"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="two"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="three"),
        ]
    )

    mapped = LMStudioConversationMapper().map_conversation(conversation)

    assert mapped.entries == [("assistant", "one\n\ntwo\n\nthree")]
