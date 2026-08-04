from typing import Protocol


class TokenCounter(Protocol):
    """Reports what a piece of text costs in the model's context window.

    Every memory layer needs this. A source reports the token cost of its fragments, and
    the pipeline decides what fits (ADR-026). The count depends on the model, because
    every model tokenizes differently, so an implementation is bound to one model.

    An implementation must not raise. A memory layer that cannot count would fail the
    turn, and the count is only ever an input to a budget decision, so an estimate is
    always better than an error.
    """

    async def count_tokens(self, text: str) -> int: ...
