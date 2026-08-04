import asyncio
import hashlib
import logging
from collections import OrderedDict

import lmstudio as lms

from rp_engine.core.memory.character_ratio_token_counter import CharacterRatioTokenCounter
from rp_engine.core.ports.context_window import ContextWindowProbe
from rp_engine.core.ports.token_counter import TokenCounter
from rp_engine.infrastructure.llm.lmstudio.provider import ensure_default_client_configured

logger = logging.getLogger(__name__)

# How many counted texts to keep. Each entry is a digest and an integer, so the cost is a
# few hundred kilobytes at this size — far less than the round trips it saves on a long
# session.
DEFAULT_CACHE_SIZE = 4096

# Context window assumed when LM Studio cannot say. Small on purpose: guessing too high
# overflows the real window.
DEFAULT_FALLBACK_CONTEXT_LENGTH = 4096


class LMStudioTokenCounter(TokenCounter, ContextWindowProbe):
    """Counts tokens with the loaded model's own tokenizer, through LM Studio.

    Both numbers come from the model handle: `count_tokens` is exact for this model, and
    `get_context_length` is the window it was loaded with. Both are calls to the LM Studio
    server, so both are cached (ADR-026).

    Caching a count is safe because a stored message never changes. The key carries the
    model name, so a model swap recounts instead of trusting a number a different
    tokenizer produced.

    Neither method raises. When the LM Studio call fails, an estimate takes over and the
    failure is logged, because a hiccup talking to localhost must never fail a turn. A
    guess is never cached, so the next call asks LM Studio again.
    """

    def __init__(
        self,
        *,
        model_name: str,
        api_host: str,
        fallback: TokenCounter | None = None,
        fallback_context_length: int = DEFAULT_FALLBACK_CONTEXT_LENGTH,
        cache_size: int = DEFAULT_CACHE_SIZE,
    ) -> None:
        if cache_size < 1:
            raise ValueError("cache_size must be at least 1.")
        if fallback_context_length < 1:
            raise ValueError("fallback_context_length must be at least 1.")
        self._model_name = model_name
        self._fallback = fallback if fallback is not None else CharacterRatioTokenCounter()
        self._fallback_context_length = fallback_context_length
        self._cache_size = cache_size
        # Keyed by model name and text digest. An instance is already bound to one model,
        # so the name is what makes that binding hold if the cache is ever shared.
        # Only ever touched from the event loop thread — the LM Studio calls are what run
        # in a worker thread, not these reads and writes — so it needs no lock.
        self._counts: OrderedDict[tuple[str, str], int] = OrderedDict()
        self._context_length: int | None = None
        ensure_default_client_configured(api_host)

    async def count_tokens(self, text: str) -> int:
        if not text:
            return 0

        key = (self._model_name, hashlib.sha256(text.encode("utf-8")).hexdigest())
        cached = self._counts.get(key)
        if cached is not None:
            self._counts.move_to_end(key)
            return cached

        try:
            count = await asyncio.to_thread(self._count_tokens_sync, text)
        except Exception:
            logger.warning(
                "LM Studio token count failed; estimating from text length instead.",
                exc_info=True,
                extra={"model_name": self._model_name},
            )
            return await self._fallback.count_tokens(text)

        self._remember(key, count)
        return count

    async def context_length(self) -> int:
        if self._context_length is not None:
            return self._context_length

        try:
            length = await asyncio.to_thread(self._context_length_sync)
        except Exception:
            logger.warning(
                "LM Studio context length request failed; assuming %d tokens instead.",
                self._fallback_context_length,
                exc_info=True,
                extra={"model_name": self._model_name},
            )
            return self._fallback_context_length

        if length < 1:
            # A window of zero would leave no room for any prompt at all, so treat it the
            # same as no answer rather than budget against it.
            logger.warning(
                "LM Studio reported a context length of %d; assuming %d tokens instead.",
                length,
                self._fallback_context_length,
                extra={"model_name": self._model_name},
            )
            return self._fallback_context_length

        self._context_length = length
        return length

    # Both handle methods are typed loosely enough that mypy sees `Any`, so coerce rather
    # than trust the annotation.
    def _count_tokens_sync(self, text: str) -> int:
        return int(lms.llm(self._model_name).count_tokens(text))

    def _context_length_sync(self) -> int:
        return int(lms.llm(self._model_name).get_context_length())

    def _remember(self, key: tuple[str, str], count: int) -> None:
        self._counts[key] = count
        self._counts.move_to_end(key)
        while len(self._counts) > self._cache_size:
            self._counts.popitem(last=False)
