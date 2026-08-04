import math

from rp_engine.core.ports.token_counter import TokenCounter

# Roughly four characters per token holds for English prose across common tokenizers. It
# is a rule of thumb, not a measurement.
DEFAULT_CHARACTERS_PER_TOKEN = 4.0


class CharacterRatioTokenCounter(TokenCounter):
    """Estimates a token count from text length.

    This is the fallback for when the real counter cannot be reached. It rounds up on
    purpose. Over-counting drops a message that would have fit; under-counting overflows
    the context window and loses the turn. Only the second one costs the player a reply.
    """

    def __init__(self, *, characters_per_token: float = DEFAULT_CHARACTERS_PER_TOKEN) -> None:
        if characters_per_token <= 0:
            raise ValueError("characters_per_token must be greater than 0.")
        self._characters_per_token = characters_per_token

    async def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, math.ceil(len(text) / self._characters_per_token))
