"""Layer 02 — the lorebook.

Authored facts about a scenario or its characters, retrieved by keyword trigger rather
than carried in every prompt (ADR-026). A wrong result here is a bug someone can point
at, not a model that drifted, because a person wrote every entry.

`recall` matches only against a short recent window, not the whole transcript. That is
what keeps an entry from firing on every later turn once its topic has come and gone:
once the triggering text scrolls past the window, the entry stops matching on its own,
with no per-session "already shown" state to invent, keep in sync with `/restart` and
`/clear`, or get wrong.
"""

from rp_engine.core.memory.fragment import PRIORITY_LOREBOOK, MemoryFragment
from rp_engine.core.memory.recall_context import MemoryObserveContext, MemoryRecallContext
from rp_engine.core.ports.lorebook_store import LorebookStore
from rp_engine.core.ports.memory_source import MemorySource
from rp_engine.core.ports.token_counter import TokenCounter

# How many trailing messages, on top of the player's current message, form the text lore
# is matched against. Short on purpose: this window is what makes a fired entry stop
# recurring once the conversation moves on (see module docstring).
RECALL_WINDOW_MESSAGES = 4

# How many entries one turn may inject. Precision over recall: it is better to omit a
# marginally relevant entry than to crowd the prompt with lore.
DEFAULT_MATCH_LIMIT = 3

LORE_LABEL = "[Lore]"


class LorebookSource(MemorySource):
    id = "lorebook"

    def __init__(
        self,
        *,
        store: LorebookStore,
        token_counter: TokenCounter,
        match_limit: int = DEFAULT_MATCH_LIMIT,
    ) -> None:
        self._store = store
        self._token_counter = token_counter
        self._match_limit = match_limit

    async def recall(self, context: MemoryRecallContext) -> tuple[MemoryFragment, ...]:
        if context.remaining_budget <= 0:
            return ()
        recall_text = self._recall_text(context)
        if not recall_text.strip():
            return ()
        entries = await self._store.find_matching(
            context.scenario_definition_id, recall_text, limit=self._match_limit
        )
        fragments = []
        for entry in entries:
            body = f"{entry.title}: {entry.content}"
            fragments.append(
                MemoryFragment(
                    source="lorebook",
                    label=LORE_LABEL,
                    body=body,
                    priority=PRIORITY_LOREBOOK,
                    tokens=await self._token_counter.count_tokens(body),
                )
            )
        return tuple(fragments)

    async def observe(self, context: MemoryObserveContext) -> None:
        """Nothing to do. A person writes this layer; the engine never learns it."""
        return None

    @staticmethod
    def _recall_text(context: MemoryRecallContext) -> str:
        """The player's message plus a short tail of what was just said.

        Not the whole transcript — see the module docstring for why that bound is what
        keeps a fired entry from recurring every later turn.
        """
        tail = context.recent_messages[-RECALL_WINDOW_MESSAGES:]
        parts = [message.content for message in tail]
        parts.append(context.current_user_message)
        return " ".join(part for part in parts if part.strip())
