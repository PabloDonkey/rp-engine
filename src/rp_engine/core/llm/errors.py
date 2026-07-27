class LLMError(RuntimeError):
    pass


class LLMConnectionError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMGenerationError(LLMError):
    pass


class EmptyGenerationError(LLMGenerationError):
    """The model returned no usable text.

    Most often a reasoning model that spent its whole token budget thinking and hit the cap
    before writing any reply. The turn is *not* persisted when this is raised: an empty
    narrator message would be replayed into every later prompt, count as a turn, and — if it
    carried `finish_reason: length` — make the next `/continue` try to resume nothing.
    """

    def __init__(self, message: str, *, finish_reason: str = "unknown") -> None:
        super().__init__(message)
        self.finish_reason = finish_reason
