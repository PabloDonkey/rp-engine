"""The stored "story so far" for one session (layer 01, ADR-026).

One row per session. It holds the running recap and the watermark that says how far the
recap reaches, which is the only state the background worker needs to answer its own
question: "is this session's summary behind?".
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """What layer 01 remembers about a session, plus how far it reaches.

    `covers_through_turn` counts **narrator replies**, the same clock the stored messages
    carry in their `turn` metadata. It is the load-bearing field: it tells the worker where
    the last pass stopped, so the next pass folds in only what came after.

    `tokens` is the recap's own cost, counted with the model that wrote it. `model_name` is
    kept beside it because both go stale together — a model swap changes the tokenizer, so
    a count from the old model is a guess about the new one.
    """

    session_id: UUID
    summary: str
    covers_through_turn: int
    tokens: int
    model_name: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        session_id: UUID,
        summary: str,
        covers_through_turn: int,
        tokens: int,
        model_name: str,
        now: datetime | None = None,
    ) -> "SessionSummary":
        stamp = now or datetime.now(UTC)
        return cls(
            session_id=session_id,
            summary=summary,
            covers_through_turn=covers_through_turn,
            tokens=tokens,
            model_name=model_name,
            created_at=stamp,
            updated_at=stamp,
        )

    def rewritten(
        self,
        *,
        summary: str,
        covers_through_turn: int,
        tokens: int,
        model_name: str,
        now: datetime | None = None,
    ) -> "SessionSummary":
        """The next version of this recap. `created_at` stays: the recap is one long-lived
        value that is rewritten, not a new record per pass."""
        return replace(
            self,
            summary=summary,
            covers_through_turn=covers_through_turn,
            tokens=tokens,
            model_name=model_name,
            updated_at=now or datetime.now(UTC),
        )
