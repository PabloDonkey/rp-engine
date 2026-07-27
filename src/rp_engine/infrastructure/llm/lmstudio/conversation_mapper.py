import lmstudio as lms

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole


class LMStudioConversationMapper:
    def map_conversation(self, conversation: Conversation) -> lms.Chat:
        system_prompt = self._build_system_prompt(conversation.messages)
        chat = lms.Chat(system_prompt)

        for message in self._collapse_narrator_runs(conversation.messages):
            if message.role == ConversationRole.USER:
                chat.add_user_message(message.content)
                continue
            # `add_assistant_response` is the SDK's name. This used to probe for
            # `add_assistant_message` — which `lms.Chat` has never had — and fall back to
            # `add_user_message`, so every narrator reply was sent to the model as if the
            # player had written it. Bind the real method directly: an AttributeError on an
            # SDK upgrade is far better than silently downgrading the role again.
            chat.add_assistant_response(message.content)

        return chat

    @classmethod
    def _collapse_narrator_runs(
        cls, messages: list[ConversationMessage]
    ) -> list[ConversationMessage]:
        """Merge runs of consecutive narrator messages into one assistant turn.

        `lms.Chat` rejects consecutive assistant responses outright
        (`Multi-part or consecutive assistant responses are not supported`), but consecutive
        narrator turns are ordinary here: `/continue` advances the story with no player turn
        between, a resumed reply is stored as its own message, and a playthrough opens with a
        narrator message. Storage splits what is conceptually one speaker's run, so this
        rejoins it.

        The join respects *why* the run was split. Text after a turn that stopped at the token
        limit is the rest of that sentence, so it is concatenated directly; anything else is a
        separate beat and gets a paragraph break.
        """
        collapsed: list[ConversationMessage] = []
        for message in messages:
            if message.role == ConversationRole.SYSTEM:
                continue
            previous = collapsed[-1] if collapsed else None
            if (
                previous is not None
                and previous.role == ConversationRole.CHARACTER
                and message.role == ConversationRole.CHARACTER
            ):
                separator = "" if previous.was_truncated else "\n\n"
                collapsed[-1] = ConversationMessage(
                    role=ConversationRole.CHARACTER,
                    content=f"{previous.content}{separator}{message.content}",
                    # Keep the *latest* metadata: `was_truncated` must describe how the merged
                    # run now ends, since that is what decides the next join and whether the
                    # conversation is still a resumable prefix.
                    metadata=message.metadata,
                )
                continue
            collapsed.append(message)
        return collapsed

    @staticmethod
    def is_prefill(conversation: Conversation) -> bool:
        """Whether this conversation should continue its final assistant message.

        Only true when the flag is set *and* the last message really is an assistant turn —
        prefilling requires something to prefill from, and a mismatch would otherwise send a
        user message as the continuation prefix.
        """
        if not conversation.continue_final_message:
            return False
        tail = [
            message
            for message in conversation.messages
            if message.role != ConversationRole.SYSTEM
        ]
        return bool(tail) and tail[-1].role == ConversationRole.CHARACTER

    @staticmethod
    def _build_system_prompt(messages: list[ConversationMessage]) -> str:
        system_parts = [
            message.content.strip()
            for message in messages
            if message.role == ConversationRole.SYSTEM and message.content.strip()
        ]
        if not system_parts:
            return "You are a roleplay character."
        return "\n\n".join(system_parts)
