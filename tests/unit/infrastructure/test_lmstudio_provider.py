from collections.abc import Callable
from typing import Any

import pytest

from rp_engine.core.conversation.conversation import Conversation
from rp_engine.core.conversation.message import ConversationMessage
from rp_engine.core.conversation.role import ConversationRole
from rp_engine.core.llm.errors import LLMConnectionError
from rp_engine.core.llm.generation import GenerationSettings
from rp_engine.infrastructure.llm.lmstudio.provider import LMStudioProvider


class FakeChat:
    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.user_messages: list[str] = []
        self.assistant_messages: list[str] = []

    def add_user_message(self, message: str) -> None:
        self.user_messages.append(message)

    def add_assistant_message(self, message: str) -> None:
        self.assistant_messages.append(message)


class FakeModel:
    def __init__(self, responder: Callable[[FakeChat], Any]) -> None:
        self._responder = responder
        self.last_config: Any = None

    def respond(self, chat: FakeChat, *, config: Any = None) -> Any:
        self.last_config = config
        return self._responder(chat)


class FakeResult:
    def __init__(self, content: str, *, finish_reason: str = "stop") -> None:
        self.content = content
        self.finish_reason = finish_reason

    def __str__(self) -> str:
        return self.content


def _conversation() -> Conversation:
    return Conversation(
        messages=[
            ConversationMessage(role=ConversationRole.SYSTEM, content="sys-a"),
            ConversationMessage(role=ConversationRole.SYSTEM, content="sys-b"),
            ConversationMessage(role=ConversationRole.CHARACTER, content="prior response"),
            ConversationMessage(role=ConversationRole.USER, content="hello"),
        ]
    )


@pytest.mark.asyncio
async def test_lmstudio_provider_uses_sdk_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    configured_hosts: list[str] = []
    model_names: list[str] = []

    def fake_configure_default_client(host: str) -> None:
        configured_hosts.append(host)

    def fake_llm(name: str) -> FakeModel:
        model_names.append(name)

        def respond(chat: FakeChat) -> FakeResult:
            return FakeResult(
                f"{chat.system_prompt}|{chat.user_messages[0]}|{chat.assistant_messages[0]}"
            )

        return FakeModel(respond)

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="http://127.0.0.1:1234",
        max_tokens=600,
        temperature=0.8,
    )
    result = await provider.generate(
        _conversation(),
        GenerationSettings(temperature=0.9, max_tokens=222),
    )

    assert configured_hosts == ["127.0.0.1:1234"]
    assert model_names == ["model-a"]
    assert result.content == "sys-a\n\nsys-b|hello|prior response"
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_lmstudio_provider_configures_client_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_hosts: list[str] = []

    def fake_configure_default_client(host: str) -> None:
        configured_hosts.append(host)

    def fake_llm(_: str) -> FakeModel:
        return FakeModel(lambda chat: chat.user_messages[0])

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="127.0.0.1:1234",
        max_tokens=600,
        temperature=0.8,
    )
    first = await provider.generate(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="one")]),
        GenerationSettings(),
    )
    second = await provider.generate(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="two")]),
        GenerationSettings(),
    )

    assert configured_hosts == ["127.0.0.1:1234"]
    assert first.content == "one"
    assert second.content == "two"


@pytest.mark.asyncio
async def test_lmstudio_provider_passes_prediction_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_instances: list[FakeModel] = []

    def fake_configure_default_client(_: str) -> None:
        return None

    def fake_llm(_: str) -> FakeModel:
        model = FakeModel(lambda _chat: "ok")
        model_instances.append(model)
        return model

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="127.0.0.1:1234",
        max_tokens=600,
        temperature=0.7,
    )

    result = await provider.generate(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="hi")]),
        GenerationSettings(max_tokens=600, temperature=0.7, top_p=0.9),
    )

    assert result.content == "ok"
    last_config = model_instances[0].last_config
    assert last_config is not None
    assert last_config.max_tokens == 600
    assert last_config.temperature == 0.7
    assert last_config.top_p_sampling == 0.9


@pytest.mark.asyncio
async def test_lmstudio_provider_unlimited_max_tokens_passes_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_instances: list[FakeModel] = []

    def fake_configure_default_client(_: str) -> None:
        return None

    def fake_llm(_: str) -> FakeModel:
        model = FakeModel(lambda _chat: "ok")
        model_instances.append(model)
        return model

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    # Both the provider default and the per-request setting are 0 (unlimited).
    provider = LMStudioProvider(
        model_name="model-a",
        api_host="127.0.0.1:1234",
        max_tokens=0,
        temperature=0.7,
    )

    await provider.generate(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="hi")]),
        GenerationSettings(max_tokens=0),
    )

    assert model_instances[0].last_config.max_tokens is None


@pytest.mark.asyncio
async def test_lmstudio_provider_maps_length_finish_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_configure_default_client(_: str) -> None:
        return None

    def fake_llm(_: str) -> FakeModel:
        return FakeModel(lambda _chat: FakeResult("partial", finish_reason="max_tokens"))

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="127.0.0.1:1234",
        max_tokens=600,
        temperature=0.7,
    )

    result = await provider.generate(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="hi")]),
        GenerationSettings(max_tokens=128, temperature=0.3),
    )

    assert result.content == "partial"
    assert result.finish_reason == "length"


@pytest.mark.asyncio
async def test_lmstudio_provider_captures_thinking_when_reasoning_marker_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_configure_default_client(_: str) -> None:
        return None

    reasoning_text = (
        "The user seems to want a dramatic reveal.__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_"
        "REASONING_END_deadbeef__Final reply text."
    )

    def fake_llm(_: str) -> FakeModel:
        return FakeModel(lambda _chat: FakeResult(reasoning_text))

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="127.0.0.1:1234",
        max_tokens=600,
        temperature=0.7,
    )

    result = await provider.generate(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="hi")]),
        GenerationSettings(max_tokens=128, temperature=0.3),
    )

    assert result.content == "Final reply text."
    assert result.thinking == "The user seems to want a dramatic reveal."


@pytest.mark.asyncio
async def test_lmstudio_provider_thinking_is_none_without_reasoning_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_configure_default_client(_: str) -> None:
        return None

    def fake_llm(_: str) -> FakeModel:
        return FakeModel(lambda _chat: FakeResult("plain reply, no reasoning marker"))

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="127.0.0.1:1234",
        max_tokens=600,
        temperature=0.7,
    )

    result = await provider.generate(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="hi")]),
        GenerationSettings(max_tokens=128, temperature=0.3),
    )

    assert result.content == "plain reply, no reasoning marker"
    assert result.thinking is None


@pytest.mark.asyncio
async def test_lmstudio_provider_maps_connectivity_errors_to_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LMStudioWebsocketError(RuntimeError):
        pass

    def fake_configure_default_client(_: str) -> None:
        return None

    def fake_llm(_: str) -> FakeModel:
        def raise_connectivity_error(_: FakeChat) -> str:
            raise LMStudioWebsocketError("LM Studio is not reachable at ws://localhost:1234/llm")

        return FakeModel(raise_connectivity_error)

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.configure_default_client",
        fake_configure_default_client,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.llm", fake_llm)
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="127.0.0.1:1234",
        max_tokens=600,
        temperature=0.7,
    )

    with pytest.raises(LLMConnectionError):
        await provider.generate(
            Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="hi")]),
            GenerationSettings(max_tokens=128, temperature=0.3),
        )


class FakeStats:
    """Mirrors the shape the LM Studio SDK actually returns.

    `PredictionResult` has no finish/stop attribute of its own — the reason lives on
    `result.stats.stop_reason`, and token counts on `*_count` fields. The older `FakeResult`
    above encodes the OpenAI-ish shape the provider used to (wrongly) assume, so it is kept
    only to prove those fallbacks still work.
    """

    def __init__(
        self,
        *,
        stop_reason: str,
        prompt_tokens_count: int | None = None,
        predicted_tokens_count: int | None = None,
        total_tokens_count: int | None = None,
    ) -> None:
        self.stop_reason = stop_reason
        self.prompt_tokens_count = prompt_tokens_count
        self.predicted_tokens_count = predicted_tokens_count
        self.total_tokens_count = total_tokens_count


class FakeSdkResult:
    """A result with no finish_reason/stop_reason of its own, exactly like the real SDK."""

    def __init__(self, content: str, stats: FakeStats) -> None:
        self.content = content
        self.stats = stats

    def __str__(self) -> str:
        return self.content


async def _generate_with(monkeypatch: pytest.MonkeyPatch, result: object) -> Any:
    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.configure_default_client",
        lambda _: None,
    )
    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.llm",
        lambda _: FakeModel(lambda _chat: result),
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.provider.lms.Chat", FakeChat)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)

    provider = LMStudioProvider(
        model_name="model-a",
        api_host="127.0.0.1:1234",
        max_tokens=600,
        temperature=0.7,
    )
    return await provider.generate(
        Conversation(messages=[ConversationMessage(role=ConversationRole.USER, content="hi")]),
        GenerationSettings(max_tokens=128),
    )


@pytest.mark.parametrize(
    ("stop_reason", "expected"),
    [
        ("eosFound", "stop"),
        ("stopStringFound", "stop"),
        ("userStopped", "stop"),
        ("toolCalls", "stop"),
        ("maxPredictedTokensReached", "length"),
        ("contextLengthReached", "context_length"),
        ("modelUnloaded", "unknown"),
        ("failed", "unknown"),
    ],
)
@pytest.mark.asyncio
async def test_finish_reason_is_read_from_stats_stop_reason(
    monkeypatch: pytest.MonkeyPatch,
    stop_reason: str,
    expected: str,
) -> None:
    result = await _generate_with(
        monkeypatch, FakeSdkResult("partial", FakeStats(stop_reason=stop_reason))
    )

    assert result.finish_reason == expected


@pytest.mark.asyncio
async def test_truncated_reply_reports_length_so_continue_can_resume_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The regression that mattered: `ChatService._should_resume` gates on `length`, so a
    missed `maxPredictedTokensReached` silently disables truncation recovery in `/continue`."""
    result = await _generate_with(
        monkeypatch,
        FakeSdkResult("cut off mid-sen", FakeStats(stop_reason="maxPredictedTokensReached")),
    )

    assert result.finish_reason == "length"


@pytest.mark.asyncio
async def test_usage_is_read_from_the_sdk_count_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = await _generate_with(
        monkeypatch,
        FakeSdkResult(
            "done",
            FakeStats(
                stop_reason="eosFound",
                prompt_tokens_count=1200,
                predicted_tokens_count=340,
                total_tokens_count=1540,
            ),
        ),
    )

    assert result.metadata["usage_prompt_tokens"] == "1200"
    assert result.metadata["usage_completion_tokens"] == "340"
    assert result.metadata["usage_total_tokens"] == "1540"


@pytest.mark.asyncio
async def test_absent_token_counts_are_omitted_rather_than_zeroed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = await _generate_with(
        monkeypatch, FakeSdkResult("done", FakeStats(stop_reason="eosFound"))
    )

    assert "usage_prompt_tokens" not in result.metadata
    assert "usage_total_tokens" not in result.metadata


def test_every_sdk_stop_reason_is_classified() -> None:
    """Drift guard. The provider's alias tables were originally written against an
    OpenAI-shaped API and silently matched nothing, which is what made every turn report
    `unknown`. If LM Studio adds or renames a stop reason, fail here rather than in prod.
    """
    import typing

    import lmstudio._sdk_models as sdk_models

    from rp_engine.infrastructure.llm.lmstudio.provider import _normalize_finish_reason

    sdk_reasons = set(typing.get_args(sdk_models.LlmPredictionStopReason))
    assert sdk_reasons, "could not read LlmPredictionStopReason from the SDK"

    # `modelUnloaded`/`failed` are intentionally unclassified — they are anomalies.
    expected_unknown = {"modelUnloaded", "failed"}
    for reason in sdk_reasons - expected_unknown:
        assert _normalize_finish_reason(reason) != "unknown", (
            f"LM Studio stop reason {reason!r} is not classified by the provider"
        )
