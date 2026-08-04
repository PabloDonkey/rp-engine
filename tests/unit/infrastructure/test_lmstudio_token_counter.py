import logging

import pytest

from rp_engine.infrastructure.llm.lmstudio.provider import LMStudioProvider
from rp_engine.infrastructure.llm.lmstudio.token_counter import LMStudioTokenCounter


class FakeModel:
    def __init__(self, *, tokens_per_call: int = 7, context_length: int = 8192) -> None:
        self.tokens_per_call = tokens_per_call
        self._context_length = context_length
        self.counted: list[str] = []
        self.context_length_calls = 0
        self.count_error: Exception | None = None
        self.context_error: Exception | None = None

    def count_tokens(self, text: str) -> int:
        if self.count_error is not None:
            raise self.count_error
        self.counted.append(text)
        return self.tokens_per_call

    def get_context_length(self) -> int:
        self.context_length_calls += 1
        if self.context_error is not None:
            raise self.context_error
        return self._context_length


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    fake_model = FakeModel()
    requested_names: list[str] = []

    def fake_llm(name: str) -> FakeModel:
        requested_names.append(name)
        return fake_model

    monkeypatch.setattr(
        "rp_engine.infrastructure.llm.lmstudio.provider.lms.configure_default_client",
        lambda host: None,
    )
    monkeypatch.setattr("rp_engine.infrastructure.llm.lmstudio.token_counter.lms.llm", fake_llm)
    monkeypatch.setattr(LMStudioProvider, "_configured_api_host", None)
    return fake_model


def _counter(
    *,
    model_name: str = "model-a",
    fallback_context_length: int = 4096,
    cache_size: int = 4096,
) -> LMStudioTokenCounter:
    return LMStudioTokenCounter(
        model_name=model_name,
        api_host="http://127.0.0.1:1234",
        fallback_context_length=fallback_context_length,
        cache_size=cache_size,
    )


@pytest.mark.asyncio
async def test_counts_with_the_loaded_model(model: FakeModel) -> None:
    counter = _counter()

    assert await counter.count_tokens("hello there") == 7
    assert model.counted == ["hello there"]


@pytest.mark.asyncio
async def test_empty_text_never_reaches_lmstudio(model: FakeModel) -> None:
    counter = _counter()

    assert await counter.count_tokens("") == 0
    assert model.counted == []


@pytest.mark.asyncio
async def test_a_counted_text_is_only_counted_once(model: FakeModel) -> None:
    counter = _counter()

    assert await counter.count_tokens("a stored message") == 7
    assert await counter.count_tokens("a stored message") == 7

    assert model.counted == ["a stored message"]


@pytest.mark.asyncio
async def test_counts_are_not_shared_between_models(model: FakeModel) -> None:
    # Every model tokenizes differently, so a count from one is worthless to the other.
    first = _counter(model_name="model-a")
    second = _counter(model_name="model-b")

    await first.count_tokens("a stored message")
    await second.count_tokens("a stored message")

    assert model.counted == ["a stored message", "a stored message"]


@pytest.mark.asyncio
async def test_cache_drops_the_oldest_entry_first(model: FakeModel) -> None:
    counter = _counter(cache_size=2)

    await counter.count_tokens("first")
    await counter.count_tokens("second")
    await counter.count_tokens("third")
    model.counted.clear()

    await counter.count_tokens("first")
    await counter.count_tokens("third")

    assert model.counted == ["first"]


@pytest.mark.asyncio
async def test_a_failed_count_falls_back_to_an_estimate(
    model: FakeModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model.count_error = RuntimeError("LM Studio is not reachable")
    counter = _counter()

    with caplog.at_level(logging.WARNING):
        # 20 characters at the default 4 characters per token.
        estimate = await counter.count_tokens("x" * 20)

    assert estimate == 5
    assert "estimating from text length" in caplog.text


@pytest.mark.asyncio
async def test_an_estimate_is_never_cached(model: FakeModel) -> None:
    model.count_error = RuntimeError("LM Studio is not reachable")
    counter = _counter()
    await counter.count_tokens("x" * 20)

    model.count_error = None

    assert await counter.count_tokens("x" * 20) == 7
    assert model.counted == ["x" * 20]


@pytest.mark.asyncio
async def test_reads_the_context_length_from_the_model(model: FakeModel) -> None:
    counter = _counter()

    assert await counter.context_length() == 8192


@pytest.mark.asyncio
async def test_context_length_is_only_read_once(model: FakeModel) -> None:
    counter = _counter()

    await counter.context_length()
    await counter.context_length()

    assert model.context_length_calls == 1


@pytest.mark.asyncio
async def test_an_unreachable_model_falls_back_to_the_assumed_window(
    model: FakeModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model.context_error = RuntimeError("LM Studio is not reachable")
    counter = _counter(fallback_context_length=2048)

    with caplog.at_level(logging.WARNING):
        assert await counter.context_length() == 2048

    assert "context length request failed" in caplog.text


@pytest.mark.asyncio
async def test_the_assumed_window_is_never_cached(model: FakeModel) -> None:
    model.context_error = RuntimeError("LM Studio is not reachable")
    counter = _counter(fallback_context_length=2048)
    await counter.context_length()

    model.context_error = None

    assert await counter.context_length() == 8192


@pytest.mark.asyncio
async def test_a_window_of_zero_is_treated_as_no_answer(
    model: FakeModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    model._context_length = 0
    counter = _counter(fallback_context_length=2048)

    with caplog.at_level(logging.WARNING):
        assert await counter.context_length() == 2048

    assert "reported a context length of 0" in caplog.text


def test_rejects_a_cache_that_holds_nothing(model: FakeModel) -> None:
    with pytest.raises(ValueError):
        _counter(cache_size=0)


def test_rejects_an_assumed_window_that_holds_nothing(model: FakeModel) -> None:
    with pytest.raises(ValueError):
        _counter(fallback_context_length=0)
