import pytest

from rp_engine.core.memory.character_ratio_token_counter import CharacterRatioTokenCounter


@pytest.mark.asyncio
async def test_empty_text_costs_nothing() -> None:
    counter = CharacterRatioTokenCounter()

    assert await counter.count_tokens("") == 0


@pytest.mark.asyncio
async def test_estimate_rounds_up() -> None:
    counter = CharacterRatioTokenCounter(characters_per_token=4.0)

    # 4 characters is exactly one token; 5 must not round back down to one.
    assert await counter.count_tokens("abcd") == 1
    assert await counter.count_tokens("abcde") == 2


@pytest.mark.asyncio
async def test_any_text_costs_at_least_one_token() -> None:
    counter = CharacterRatioTokenCounter(characters_per_token=100.0)

    assert await counter.count_tokens("a") == 1


@pytest.mark.asyncio
async def test_estimate_scales_with_length() -> None:
    counter = CharacterRatioTokenCounter(characters_per_token=4.0)

    assert await counter.count_tokens("x" * 400) == 100


def test_ratio_must_be_positive() -> None:
    with pytest.raises(ValueError):
        CharacterRatioTokenCounter(characters_per_token=0.0)
