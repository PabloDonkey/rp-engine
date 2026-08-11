import re
from collections.abc import Sequence

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.ports import LLMProvider
from rp_engine.core.ports.conversation_summarizer import ConversationSummarizer

# The recap is a record, not a performance: low temperature, because the one thing this
# call must not do is write something the transcript does not say.
SUMMARY_TEMPERATURE = 0.2
SUMMARY_TOP_P = 0.9
# Tokens per requested word, with room to spare. The cap is a backstop against a model that
# ignores the word target; the caller counts the result and condenses it if it must.
TOKENS_PER_WORD = 3

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
    def __init__(self, *, llm_provider: LLMProvider) -> None:
        self._llm_provider = llm_provider

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
        response = await self._llm_provider.generate(
            conversation,
            GenerationSettings(
                temperature=SUMMARY_TEMPERATURE,
                max_tokens=target_words * TOKENS_PER_WORD,
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
