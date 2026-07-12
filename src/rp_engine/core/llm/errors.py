class LLMError(RuntimeError):
    pass


class LLMConnectionError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMGenerationError(LLMError):
    pass
