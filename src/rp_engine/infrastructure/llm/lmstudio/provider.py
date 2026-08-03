import asyncio
import logging
import re
from threading import Lock
from typing import Any, ClassVar
from urllib.parse import urlparse

import lmstudio as lms

# Neither name is re-exported from the `lmstudio` package root in SDK 1.5.0, but both are
# part of the documented wire schema (`llm.prediction.reasoning.parsing` and the
# `reasoningType` fragment field) — the generated model module is where they live.
from lmstudio._sdk_models import LlmPredictionFragment, LlmReasoningParsing

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.llm.errors import (
    LLMConnectionError,
    LLMError,
    LLMGenerationError,
    LLMTimeoutError,
)
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
        reasoning_start_tag: str = "",
        reasoning_end_tag: str = "",
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
        self._reasoning_parsing = _build_reasoning_parsing(reasoning_start_tag, reasoning_end_tag)
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
        except LLMError:
            # Already diagnosed (e.g. reasoning that could not be separated). Re-raise as-is
            # so the catch-all below does not flatten it into a generic failure.
            raise
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
        # Prefill needs no special call: mapping a character message to
        # `add_assistant_response` already leaves the chat assistant-final, which LM Studio
        # continues in place. What can silently break it is the *shape* not matching the
        # intent — e.g. a memory strategy that trims or reorders so the truncated reply is
        # no longer last. Then the model opens a new turn and re-plans, which is the exact
        # failure prefill exists to remove, so say so rather than fail quietly.
        if conversation.continue_final_message and not self._conversation_mapper.is_prefill(
            conversation
        ):
            logger.warning(
                "Resume requested but the conversation is not assistant-final; "
                "the model will open a new turn instead of continuing.",
                extra={"model_name": self._model_name},
            )
        config = self._get_config(settings)
        logger.info(f"LmStudio.generate with config {config}")

        # LM Studio classifies every fragment it streams as reasoning or not; collecting
        # them is how thinking gets separated from prose. `respond` still returns the whole
        # result — the callback runs alongside it, so this is not a streaming API change.
        collector = _ReasoningFragmentCollector()
        result = model.respond(chat, config=config, on_prediction_fragment=collector)

        clean_text, thinking = self._separate_reasoning(
            result,
            collector,
            keep_leading_space=conversation.continue_final_message,
        )
        logger.info(f"LLM response content: {clean_text}")

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
            thinking=thinking,
        )

    def _separate_reasoning(
        self,
        result: Any,
        collector: "_ReasoningFragmentCollector",
        *,
        keep_leading_space: bool = False,
    ) -> tuple[str, str | None]:
        """Split the model's thinking from the prose the player will read.

        The fragment classification LM Studio streams (`reasoningType`) is the supported
        signal and the only one that survives a change in how reasoning is delimited. This
        used to split `result.content` on
        `__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_<hex>__` — an internal, synthetic
        marker with no compatibility promise. Had it changed shape the split would have
        silently no-opped and delivered the model's entire reasoning to the player as the
        story, so the marker survives only as a fallback that says so when it fires.

        Empty prose with reasoning captured is left to `ChatService._require_content`, which
        rejects the turn as an `EmptyGenerationError` — that is the reasoning-only case, and
        it must never reach the player, but it is also not this layer's decision to make.

        `keep_leading_space` is set for a prefill continuation, where the reply resumes
        mid-sentence and the space in front of it is part of the text: stripping it glues
        "he walked" to "to the door". It applies only when nothing was classified as
        reasoning — which is the normal prefill case, per the docstring of
        `ConversationBuilder.build_resume` — so no leftover newline from a reasoning
        boundary can be mistaken for meaningful whitespace.
        """
        # A structured prediction's user-facing value is `result.parsed`, which fragments do
        # not reassemble into; leave those to `_extract_content`.
        if collector.saw_fragments and not getattr(result, "structured", False):
            reasoning = collector.reasoning.strip()
            prose = self._trim_prose(
                collector.prose,
                keep_leading_space=keep_leading_space and not reasoning,
            )
            if not _INTERNAL_MARKER_HINT.search(prose):
                return prose, reasoning or None
            # LM Studio handed back a marker inside text it classified as prose, i.e. it did
            # not recognize this model's reasoning delimiters. Fall through to the split.
            logger.warning(
                "Reasoning marker found in text LM Studio classified as prose; "
                "falling back to marker splitting.",
                extra={"model_name": self._model_name},
            )
            content = prose
        else:
            content = self._extract_content(result)

        parts = _REASONING_END_MARKER.split(content)
        if len(parts) > 1:
            logger.warning(
                "Separated reasoning by internal LM Studio marker; the supported "
                "fragment classification did not report any reasoning.",
                extra={"model_name": self._model_name},
            )
        # Anything the classification did catch is still the model's thinking, even when the
        # rest had to be recovered from the marker — keep both rather than pick one.
        reasoning_parts = [collector.reasoning, *parts[:-1]]
        thinking = "\n".join(part.strip() for part in reasoning_parts if part.strip()) or None
        clean_text = self._trim_prose(
            parts[-1],
            keep_leading_space=keep_leading_space and thinking is None,
        )

        # Both paths failed if a marker is still in there: the text is an unsplit blob of
        # reasoning, and handing it to the player as the story is worse than no reply.
        if _INTERNAL_MARKER_HINT.search(clean_text):
            msg = (
                "LM Studio returned reasoning that could not be separated from the reply; "
                "refusing to deliver it as prose."
            )
            raise LLMGenerationError(msg)

        return clean_text, thinking

    @staticmethod
    def _trim_prose(text: str, *, keep_leading_space: bool) -> str:
        """Trim generated prose, optionally keeping the space a continuation starts with.

        Only a single leading space or newline survives. More than that is model padding,
        not sentence glue.
        """
        trimmed = text.rstrip()
        if not keep_leading_space:
            return trimmed.strip()
        leading = trimmed[: len(trimmed) - len(trimmed.lstrip())]
        return leading[:1] + trimmed.lstrip()

    def _get_config(self, settings: GenerationSettings) -> lms.LlmPredictionConfig:
        # A positive per-request cap wins; otherwise fall back to the configured default.
        # A resolved cap of 0 means "no limit" — pass None so LM Studio leaves it unbounded.
        resolved_max_tokens = settings.max_tokens or self._default_max_tokens
        # `stop_strings` is the SDK's field name. This used to probe `stop`/`stop_sequences`/
        # `stop_strings` in order and set the first that existed — the same shape as the
        # assistant-role bug, and correct only by accident since no earlier name exists.
        return lms.LlmPredictionConfig(
            max_tokens=resolved_max_tokens if resolved_max_tokens > 0 else None,
            temperature=(
                settings.temperature if settings.temperature >= 0 else self._default_temperature
            ),
            top_k_sampling=self._top_k_sampling,
            repeat_penalty=self._repeat_penalty,
            top_p_sampling=settings.top_p if settings.top_p is not None else self._top_p_sampling,
            min_p_sampling=self._min_p_sampling,
            stop_strings=list(settings.stop_sequences) if settings.stop_sequences else None,
            # None leaves LM Studio's per-model reasoning delimiters in place, which is what
            # the fragment classification is derived from. Only set the tags when a model
            # LM Studio does not know about needs them declared.
            reasoning_parsing=self._reasoning_parsing,
        )

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
        """Read why generation stopped.

        The LM Studio SDK carries this as `result.stats.stop_reason` — `PredictionResult`
        itself has no finish/stop attribute. The other probes are tolerated fallbacks for
        shape drift, not the expected path.
        """
        stats = getattr(result, "stats", None)
        if stats is not None:
            stats_stop = getattr(stats, "stop_reason", None)
            if isinstance(stats_stop, str):
                return _normalize_finish_reason(stats_stop)
            stats_finish = getattr(stats, "finish_reason", None)
            if isinstance(stats_finish, str):
                return _normalize_finish_reason(stats_finish)

        for attribute in ("finish_reason", "stop_reason"):
            candidate = getattr(result, attribute, None)
            if isinstance(candidate, str):
                return _normalize_finish_reason(candidate)

        return "unknown"

    @staticmethod
    def _extract_usage_metadata(stats: Any) -> dict[str, str]:
        """Token counts from `LlmPredictionStats`.

        The `*_count` names are the SDK's; the bare names are tolerated fallbacks.
        """
        usage: dict[str, str] = {}
        candidates = {
            "usage_prompt_tokens": ("prompt_tokens_count", "prompt_tokens", "input_tokens"),
            "usage_completion_tokens": (
                "predicted_tokens_count",
                "completion_tokens",
                "output_tokens",
            ),
            "usage_total_tokens": ("total_tokens_count", "total_tokens"),
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


class _ReasoningFragmentCollector:
    """Sorts streamed prediction fragments into prose and reasoning.

    LM Studio tags every fragment with a `reasoningType`, so the split comes from the
    server's own parse rather than from string-matching the assembled reply. The two tag
    types carry the delimiters themselves (`<think>` and friends) and belong in neither
    bucket.
    """

    def __init__(self) -> None:
        self._prose: list[str] = []
        self._reasoning: list[str] = []
        self.saw_fragments = False

    def __call__(self, fragment: LlmPredictionFragment) -> None:
        self.saw_fragments = True
        reasoning_type = getattr(fragment, "reasoning_type", "none")
        if reasoning_type == "reasoning":
            self._reasoning.append(fragment.content)
        elif reasoning_type == "none":
            self._prose.append(fragment.content)

    @property
    def prose(self) -> str:
        return "".join(self._prose)

    @property
    def reasoning(self) -> str:
        return "".join(self._reasoning)


def _build_reasoning_parsing(start_tag: str, end_tag: str) -> LlmReasoningParsing | None:
    """Declare the reasoning delimiters, or leave LM Studio's per-model defaults alone.

    Forcing tags on every prediction would break any model whose reasoning is delimited
    differently, so this is opt-in. Half a pair is always a misconfiguration — parsing
    would key off a start with no end, or the reverse — so say so at startup rather than
    at the first generation.
    """
    if not start_tag and not end_tag:
        return None
    if not start_tag or not end_tag:
        msg = (
            "LM Studio reasoning tags must be configured as a pair: "
            "RP_ENGINE_LMSTUDIO_REASONING_START_TAG and RP_ENGINE_LMSTUDIO_REASONING_END_TAG."
        )
        raise ValueError(msg)
    return LlmReasoningParsing(enabled=True, start_string=start_tag, end_string=end_tag)


def _normalize_api_host(api_host: str) -> str:
    parsed = urlparse(api_host)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc
    return api_host


# The exact internal marker LM Studio has been observed to synthesize, used only to split a
# reply the supported fragment classification did not separate. `_INTERNAL_MARKER_HINT` is
# deliberately looser: it recognizes a marker whose shape drifted well enough to refuse the
# text, which is the whole failure this fallback exists to make loud.
_REASONING_END_MARKER = re.compile(r"__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_[a-f0-9]+__")
_INTERNAL_MARKER_HINT = re.compile(r"__LM_STUDIO_INTERNAL_[A-Za-z0-9_]*__")


# LM Studio's own stop-reason vocabulary (`LlmPredictionStopReason`), lowercased, plus the
# OpenAI-style aliases other backends use. `modelUnloaded` and `failed` are deliberately
# absent: they are anomalies, and reporting them as a clean stop would be a lie.
_STOP_REASONS = frozenset(
    {
        "eosfound",
        "stopstringfound",
        "userstopped",
        "toolcalls",
        # Non-LM-Studio aliases.
        "stop",
        "eos",
        "completed",
        "end_turn",
    }
)
_LENGTH_REASONS = frozenset(
    {
        "maxpredictedtokensreached",
        # Non-LM-Studio aliases.
        "length",
        "max_tokens",
        "token_limit",
    }
)
_CONTEXT_LENGTH_REASONS = frozenset({"contextlengthreached"})


def _normalize_finish_reason(reason: str) -> FinishReason:
    normalized = reason.strip().lower()
    if normalized in _STOP_REASONS:
        return "stop"
    if normalized in _LENGTH_REASONS:
        return "length"
    if normalized in _CONTEXT_LENGTH_REASONS:
        return "context_length"
    return "unknown"


def _is_lmstudio_connection_error(exc: Exception) -> bool:
    class_name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    return "lmstudio" in class_name and (
        "clienterror" in class_name
        or "websocketerror" in class_name
        or "not reachable" in message
        or "connection attempts failed" in message
    )
