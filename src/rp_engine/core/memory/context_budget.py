from rp_engine.core.ports.context_window import ContextWindowProbe


class ContextBudget:
    """How many tokens the prompt may spend, as a share of the model's context window.

    The window is read from the model; only the share is configured (ADR-026). The rest of
    the window is what the reply is written into, so a share of 1.0 leaves no room to
    answer.

    The number is resolved on demand rather than stored, because the probe behind it may
    have had to guess the first time it was asked.
    """

    def __init__(self, *, context_window: ContextWindowProbe, share: float) -> None:
        if not 0.0 < share <= 1.0:
            raise ValueError("share must be greater than 0 and at most 1.")
        self._context_window = context_window
        self._share = share

    async def total_tokens(self) -> int:
        context_length = await self._context_window.context_length()
        return max(1, int(context_length * self._share))
