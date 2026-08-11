from collections.abc import Sequence
from typing import Protocol

from rp_engine.core.conversation.message import ConversationMessage


class ConversationSummarizer(Protocol):
    """Writes the running recap layer 01 stores.

    Both methods take a word target rather than a token budget. The caller owns the budget
    and converts it; a model follows an instruction about words far better than one about
    tokens, and neither instruction is obeyed exactly, which is why the caller counts the
    result afterwards.

    An implementation must return plain text with no preamble, and must invent nothing that
    is not in what it was given.
    """

    async def summarize_story_so_far(
        self,
        *,
        previous_summary: str,
        new_messages: Sequence[ConversationMessage],
        target_words: int,
    ) -> str:
        """Fold `new_messages` into `previous_summary` and return the whole recap.

        `previous_summary` is empty on the first pass. It is never dropped afterwards: the
        transcript it came from has already left the window, so the previous recap is the
        only record of that part of the story.
        """
        ...

    async def condense_story_summary(self, *, summary: str, target_words: int) -> str:
        """Shorten a recap that has outgrown its budget, keeping what still matters."""
        ...
