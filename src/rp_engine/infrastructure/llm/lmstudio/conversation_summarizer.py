import logging
import re
from collections.abc import Sequence

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.ports import LLMProvider
from rp_engine.core.ports.conversation_summarizer import ConversationSummarizer

logger = logging.getLogger(__name__)

# The recap is a record, not a performance: low temperature, because the one thing this
# call must not do is write something the transcript does not say.
SUMMARY_TEMPERATURE = 0.2
SUMMARY_TOP_P = 0.9
# What the summarizer may generate, in tokens. It is not derived from the word target, and
# that was a real bug: a reasoning model writes its thinking into the same budget, so a cap
# sized for the recap alone is spent before the recap starts and the reply arrives empty
# (the same failure S027 fixed on the story path). This covers the thinking and the recap.
#
# The number is measured, not guessed. On `gemma-4-26b-a4b-it-heretic`, folding five turns
# came back empty at 3072 and wrote a 233-token recap at 6144. A cap costs nothing when the
# model stops early, so it is set where the first attempt usually succeeds.
DEFAULT_SUMMARY_MAX_TOKENS = 6144

SUMMARY_SYSTEM_PROMPT = (
    "You keep the running record of a roleplay story. You write faithful, compact recaps "
    "in plain text and never continue the story yourself."
)

_RULES = (
    "- Use only information present in the text you are given.\n"
    "- No invented facts, no speculation, no internal reasoning, no commentary.\n"
    "- Write in the third person, in the past tense.\n"
    "- Keep who did what, what changed, what was agreed or refused, and what is unresolved.\n"
    "- Drop small talk, repeated description and exact wording.\n"
    "- Plain prose only: no headings, no bullet points, no preamble.\n"
)


class LMStudioConversationSummarizer(ConversationSummarizer):
    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        max_tokens: int = DEFAULT_SUMMARY_MAX_TOKENS,
    ) -> None:
        self._llm_provider = llm_provider
        self._max_tokens = max_tokens

    async def summarize_story_so_far(
        self,
        *,
        previous_summary: str,
        new_messages: Sequence[ConversationMessage],
        target_words: int,
    ) -> str:
        transcript = self._format_messages(new_messages)
        if not transcript:
            return previous_summary.strip()

        earlier = previous_summary.strip()
        prompt = (
            "Update the running recap of this roleplay story so that it also covers the "
            "new transcript below.\n"
            "The recap replaces the transcript in the model's context, so anything it "
            "leaves out is lost to the story.\n\n"
            "Requirements:\n"
            f"{_RULES}"
            "- Keep what the earlier recap already established; do not restart it.\n"
            f"- Output one recap of about {target_words} words, covering both parts.\n\n"
            f"Earlier recap:\n{earlier or '(none yet — this is the start of the story)'}\n\n"
            f"New transcript:\n{transcript}"
        )
        return await self._generate(prompt=prompt, target_words=target_words)

    async def condense_story_summary(self, *, summary: str, target_words: int) -> str:
        text = summary.strip()
        if not text:
            return ""
        prompt = (
            "Shorten the running recap of this roleplay story. It has grown past the room "
            "the story has for it.\n\n"
            "Requirements:\n"
            f"{_RULES}"
            "- Keep the events, people and unresolved threads that still shape the story; "
            "compress or drop what has been settled.\n"
            f"- Output one recap of about {target_words} words.\n\n"
            f"Recap to shorten:\n{text}"
        )
        return await self._generate(prompt=prompt, target_words=target_words)

    async def _generate(self, *, prompt: str, target_words: int) -> str:
        """Ask for one recap, and ask twice if the first reply carries no text.

        How much a model spends on reasoning varies with the input, so no single cap is
        safe. One retry at double the cap costs a background call and turns "the recap
        silently stopped updating" into "the recap took a little longer".
        """
        conversation = Conversation(
            messages=[
                ConversationMessage(
                    role=ConversationRole.SYSTEM,
                    content=SUMMARY_SYSTEM_PROMPT,
                ),
                ConversationMessage(role=ConversationRole.USER, content=prompt),
            ],
            metadata={"purpose": "rolling_summary"},
        )
        summary = await self._attempt(conversation, max_tokens=self._max_tokens)
        if summary:
            return summary

        logger.warning(
            "The summarizer wrote no recap within %d tokens; retrying once at %d.",
            self._max_tokens,
            self._max_tokens * 2,
            extra={"max_tokens": self._max_tokens},
        )
        return await self._attempt(conversation, max_tokens=self._max_tokens * 2)

    async def _attempt(self, conversation: Conversation, *, max_tokens: int) -> str:
        response = await self._llm_provider.generate(
            conversation,
            GenerationSettings(
                temperature=SUMMARY_TEMPERATURE,
                max_tokens=max_tokens,
                top_p=SUMMARY_TOP_P,
            ),
        )
        return self._normalize_summary(response.content)

    @staticmethod
    def _format_messages(messages: Sequence[ConversationMessage]) -> str:
        lines: list[str] = []
        for message in messages:
            content = message.content.strip()
            if not content:
                continue
            role = "Player" if message.role == ConversationRole.USER else "Story"
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _normalize_summary(raw: str) -> str:
        compact = re.sub(r"\s+", " ", raw).strip()
        return compact
