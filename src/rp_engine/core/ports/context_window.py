from typing import Protocol


class ContextWindowProbe(Protocol):
    """Reports how many tokens the loaded model can hold at once.

    ADR-026 reads this number from the model instead of configuring it: a hand-set token
    number goes silently wrong the moment a model with a smaller window is loaded.

    An implementation must not raise, for the same reason `TokenCounter` must not.
    """

    async def context_length(self) -> int: ...
