import re

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.ports import LLMProvider
from rp_engine.core.ports.conversation_summarizer import ConversationSummarizer


class LMStudioConversationSummarizer(ConversationSummarizer):
    def __init__(self, *, llm_provider: LLMProvider) -> None:
        self._llm_provider = llm_provider

    async def summarize_recent_conversation(
        self,
        *,
        recent_messages: list[ConversationMessage],
    ) -> str:
        transcript = self._format_recent_messages(recent_messages)
        if not transcript:
            return ""

        prompt = (
            "Summarize this roleplay context for a character handoff.\n"
            "Requirements:\n"
            "- Use only information present in the transcript.\n"
            "- No invented facts, no speculation, no internal reasoning.\n"
            "- Mention the user's current situation and unresolved topics.\n"
            "- Keep it short and useful for continuity.\n"
            "- Output 50-150 words in plain text.\n\n"
            "Transcript (latest messages only):\n"
            f"{transcript}"
        )

        conversation = Conversation(
            messages=[
                ConversationMessage(
                    role=ConversationRole.SYSTEM,
                    content=(
                        "You produce concise, faithful transition summaries for roleplay "
                        "character switches."
                    ),
                ),
                ConversationMessage(role=ConversationRole.USER, content=prompt),
            ],
            metadata={"purpose": "character_switch_summary"},
        )
        response = await self._llm_provider.generate(
            conversation,
            GenerationSettings(
                temperature=0.2,
                max_tokens=220,
                top_p=0.9,
            ),
        )
        return self._normalize_summary(response.content)

    @staticmethod
    def _format_recent_messages(messages: list[ConversationMessage]) -> str:
        lines: list[str] = []
        for message in messages:
            content = message.content.strip()
            if not content:
                continue
            role = "User" if message.role == ConversationRole.USER else "Character"
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _normalize_summary(raw: str) -> str:
        compact = re.sub(r"\s+", " ", raw).strip()
        return compact