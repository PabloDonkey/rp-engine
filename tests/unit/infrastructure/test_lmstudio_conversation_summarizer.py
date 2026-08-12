import pytest

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.llm.response import LLMResponse
from rp_engine.infrastructure.llm.lmstudio.conversation_summarizer import (
    LMStudioConversationSummarizer,
)


class FakeProvider:
    """Answers with the replies the test queues, and records the caps it was asked for."""

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.caps: list[int | None] = []

    async def generate(
        self, conversation: Conversation, settings: GenerationSettings
    ) -> LLMResponse:
        self.caps.append(settings.max_tokens)
        content = self._replies.pop(0) if self._replies else ""
        return LLMResponse(content=content)


def _turns() -> list[ConversationMessage]:
    return [
        ConversationMessage(role=ConversationRole.USER, content="I search the room."),
        ConversationMessage(role=ConversationRole.CHARACTER, content="You find a rusted key."),
    ]


@pytest.mark.asyncio
async def test_the_recap_is_asked_for_within_the_configured_cap() -> None:
    provider = FakeProvider("They searched the room and found a key.")
    summarizer = LMStudioConversationSummarizer(llm_provider=provider, max_tokens=1500)

    summary = await summarizer.summarize_story_so_far(
        previous_summary="", new_messages=_turns(), target_words=250
    )

    assert summary == "They searched the room and found a key."
    # The cap covers the reply, not the word target: both come out of one budget.
    assert provider.caps == [1500]


@pytest.mark.asyncio
async def test_an_empty_reply_is_retried_once_at_double_the_cap() -> None:
    """The failure this retry exists for.

    A reasoning model can spend the whole output budget thinking and write no recap. The
    reply arrives empty, the pass stores nothing, and the recap silently stops updating.
    How much a model spends on reasoning varies with the input, so no single cap is safe.
    """
    provider = FakeProvider("", "They searched the room and found a key.")
    summarizer = LMStudioConversationSummarizer(llm_provider=provider, max_tokens=1500)

    summary = await summarizer.summarize_story_so_far(
        previous_summary="", new_messages=_turns(), target_words=250
    )

    assert summary == "They searched the room and found a key."
    assert provider.caps == [1500, 3000]


@pytest.mark.asyncio
async def test_two_empty_replies_give_up_rather_than_loop() -> None:
    provider = FakeProvider("", "")
    summarizer = LMStudioConversationSummarizer(llm_provider=provider, max_tokens=1500)

    summary = await summarizer.summarize_story_so_far(
        previous_summary="", new_messages=_turns(), target_words=250
    )

    assert summary == ""
    assert len(provider.caps) == 2


@pytest.mark.asyncio
async def test_nothing_to_fold_asks_the_model_nothing() -> None:
    provider = FakeProvider("unused")
    summarizer = LMStudioConversationSummarizer(llm_provider=provider)

    summary = await summarizer.summarize_story_so_far(
        previous_summary="They crossed the river.", new_messages=[], target_words=250
    )

    assert summary == "They crossed the river."
    assert provider.caps == []


@pytest.mark.asyncio
async def test_condensing_carries_the_earlier_recap_into_the_prompt() -> None:
    provider = FakeProvider("Shorter.")
    summarizer = LMStudioConversationSummarizer(llm_provider=provider)

    summary = await summarizer.condense_story_summary(
        summary="A very long recap of the story.", target_words=100
    )

    assert summary == "Shorter."


@pytest.mark.asyncio
async def test_condensing_nothing_asks_the_model_nothing() -> None:
    provider = FakeProvider("unused")
    summarizer = LMStudioConversationSummarizer(llm_provider=provider)

    assert await summarizer.condense_story_summary(summary="   ", target_words=100) == ""
    assert provider.caps == []


@pytest.mark.asyncio
async def test_the_recap_comes_back_as_one_block_of_plain_text() -> None:
    provider = FakeProvider("  They crossed\n\n the river,\tand lost the map.  ")
    summarizer = LMStudioConversationSummarizer(llm_provider=provider)

    summary = await summarizer.summarize_story_so_far(
        previous_summary="", new_messages=_turns(), target_words=250
    )

    assert summary == "They crossed the river, and lost the map."
