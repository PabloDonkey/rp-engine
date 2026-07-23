import asyncio
import logging
import re
from threading import Lock
from typing import Any, ClassVar
from urllib.parse import urlparse

import lmstudio as lms

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.llm.errors import LLMConnectionError, LLMGenerationError, LLMTimeoutError
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.core.llm.response import FinishReason, LLMResponse
from rp_engine.core.ports import LLMProvider
from rp_engine.infrastructure.llm.lmstudio.conversation_mapper import LMStudioConversationMapper

logger = logging.getLogger(__name__)


class LMStudioProvider(LLMProvider):
    _client_lock: ClassVar[Lock] = Lock()
    _configured_api_host: ClassVar[str | None] = None

    def __init__(
        self,
        *,
        model_name: str,
        api_host: str,
        max_tokens: int,
        temperature: float,
        top_k_sampling: int = 40,
        repeat_penalty: float = 1.1,
        top_p_sampling: float = 0.95,
        min_p_sampling: float = 0.05,
        conversation_mapper: LMStudioConversationMapper | None = None,
    ) -> None:
        self._model_name = model_name
        self._api_host = _normalize_api_host(api_host)
        self._default_max_tokens = max_tokens
        self._default_temperature = temperature
        self._top_k_sampling = top_k_sampling
        self._repeat_penalty = repeat_penalty
        self._top_p_sampling = top_p_sampling
        self._min_p_sampling = min_p_sampling
        self._conversation_mapper = (
            conversation_mapper if conversation_mapper is not None else LMStudioConversationMapper()
        )
        self._ensure_default_client_configured(self._api_host)

    async def generate(
        self,
        conversation: Conversation,
        settings: GenerationSettings,
    ) -> LLMResponse:
        logger.info("LLM request sent", extra={"model_name": self._model_name})
        try:
            return await asyncio.to_thread(self._generate_sync, conversation, settings)
        except TimeoutError as exc:
            logger.exception("LLM timeout", extra={"model_name": self._model_name})
            raise LLMTimeoutError("Timed out waiting for LM Studio response.") from exc
        except (ConnectionError, OSError) as exc:
            logger.exception("LLM connection failure", extra={"model_name": self._model_name})
            raise LLMConnectionError("Unable to connect to LM Studio.") from exc
        except Exception as exc:
            if _is_lmstudio_connection_error(exc):
                logger.exception("LLM connection failure", extra={"model_name": self._model_name})
                raise LLMConnectionError("Unable to connect to LM Studio.") from exc
            logger.exception("LLM generation failure", extra={"model_name": self._model_name})
            raise LLMGenerationError("LM Studio failed to generate a response.") from exc

    def _generate_sync(
        self,
        conversation: Conversation,
        settings: GenerationSettings,
    ) -> LLMResponse:
        model = lms.llm(self._model_name)
        chat = self._conversation_mapper.map_conversation(conversation)
        config = self._get_config(settings)
        logger.info(
            f"LmStudio.generate with config {config}"
        )

        result = model.respond(chat, config=config)

        content = self._extract_content(result)
        logger.info(f"LLM response content: {content}")

        # Clean the LM Studio internal reasoning string out of the final text
        parts = re.split(
            r"__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_[a-f0-9]+__", content
        )
        clean_text = parts[-1].strip()

        stats = getattr(result, "stats", None)
        metadata = {
            "provider": "lmstudio",
            "model_name": self._model_name,
        }
        if stats is not None:
            metadata["stats"] = str(stats)
            metadata.update(self._extract_usage_metadata(stats))

        return LLMResponse(
            content=clean_text,
            finish_reason=self._extract_finish_reason(result),
            metadata=metadata,
        )

    def _get_config(self, settings: GenerationSettings) -> lms.LlmPredictionConfig:
        # A positive per-request cap wins; otherwise fall back to the configured default.
        # A resolved cap of 0 means "no limit" — pass None so LM Studio leaves it unbounded.
        resolved_max_tokens = settings.max_tokens or self._default_max_tokens
        config = lms.LlmPredictionConfig(
            max_tokens=resolved_max_tokens if resolved_max_tokens > 0 else None,
            temperature=(
                settings.temperature if settings.temperature >= 0 else self._default_temperature
            ),
            top_k_sampling=self._top_k_sampling,
            repeat_penalty=self._repeat_penalty,
            top_p_sampling=settings.top_p if settings.top_p is not None else self._top_p_sampling,
            min_p_sampling=self._min_p_sampling,
        )
        if settings.stop_sequences:
            stop_values = list(settings.stop_sequences)
            for attr in ("stop", "stop_sequences", "stop_strings"):
                if hasattr(config, attr):
                    setattr(config, attr, stop_values)
                    break
        return config

    @staticmethod
    def _extract_content(result: Any) -> str:
        """Extract the primary, user-facing content from the raw model response.

        `model.respond` may hand back an object exposing `.content`, a mapping with a
        "content" key, or a bare string. Normalize all three to a string.
        """
        if isinstance(result, dict):
            content = result.get("content")
        elif hasattr(result, "content"):
            content = result.content
        else:
            content = None

        if isinstance(content, str):
            return content

        return str(result)

    @staticmethod
    def _extract_finish_reason(result: Any) -> FinishReason:
        finish_reason = getattr(result, "finish_reason", None)
        if isinstance(finish_reason, str):
            return _normalize_finish_reason(finish_reason)

        stop_reason = getattr(result, "stop_reason", None)
        if isinstance(stop_reason, str):
            return _normalize_finish_reason(stop_reason)

        stats = getattr(result, "stats", None)
        if stats is not None:
            stats_finish = getattr(stats, "finish_reason", None)
            if isinstance(stats_finish, str):
                return _normalize_finish_reason(stats_finish)

        return "unknown"

    @staticmethod
    def _extract_usage_metadata(stats: Any) -> dict[str, str]:
        usage: dict[str, str] = {}
        candidates = {
            "usage_prompt_tokens": ("prompt_tokens", "input_tokens"),
            "usage_completion_tokens": ("completion_tokens", "output_tokens"),
            "usage_total_tokens": ("total_tokens",),
        }
        for metadata_key, attrs in candidates.items():
            value: object | None = None
            for attr in attrs:
                candidate = getattr(stats, attr, None)
                if isinstance(candidate, int):
                    value = candidate
                    break
            if isinstance(value, int):
                usage[metadata_key] = str(value)
        return usage

    @classmethod
    def _ensure_default_client_configured(cls, api_host: str) -> None:
        with cls._client_lock:
            configured_host = cls._configured_api_host
            if configured_host is None:
                lms.configure_default_client(api_host)
                cls._configured_api_host = api_host
                return

            if configured_host != api_host:
                msg = (
                    "LM Studio client is already configured for "
                    f"{configured_host} and cannot be reconfigured to {api_host}."
                )
                raise ValueError(msg)


def _normalize_api_host(api_host: str) -> str:
    parsed = urlparse(api_host)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc
    return api_host


def _normalize_finish_reason(reason: str) -> FinishReason:
    normalized = reason.strip().lower()
    if normalized in {"stop", "eos", "completed", "end_turn"}:
        return "stop"
    if normalized in {"length", "max_tokens", "token_limit"}:
        return "length"
    return "unknown"


def _is_lmstudio_connection_error(exc: Exception) -> bool:
    class_name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    return (
        "lmstudio" in class_name
        and (
            "clienterror" in class_name
            or "websocketerror" in class_name
            or "not reachable" in message
            or "connection attempts failed" in message
        )
    )


