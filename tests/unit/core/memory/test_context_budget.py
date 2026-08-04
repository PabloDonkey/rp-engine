import pytest

from rp_engine.core.memory.context_budget import ContextBudget


class FakeContextWindow:
    def __init__(self, length: int) -> None:
        self.length = length
        self.calls = 0

    async def context_length(self) -> int:
        self.calls += 1
        return self.length


@pytest.mark.asyncio
async def test_budget_is_a_share_of_the_model_window() -> None:
    budget = ContextBudget(context_window=FakeContextWindow(8192), share=0.7)

    assert await budget.total_tokens() == 5734


@pytest.mark.asyncio
async def test_full_share_spends_the_whole_window() -> None:
    budget = ContextBudget(context_window=FakeContextWindow(2048), share=1.0)

    assert await budget.total_tokens() == 2048


@pytest.mark.asyncio
async def test_budget_is_never_zero() -> None:
    # A tiny window and a small share round to nothing, which would leave no room for any
    # prompt at all.
    budget = ContextBudget(context_window=FakeContextWindow(1), share=0.01)

    assert await budget.total_tokens() == 1


@pytest.mark.asyncio
async def test_budget_re_reads_the_window() -> None:
    # The probe may have had to guess the first time, so the budget must not freeze the
    # first answer it got.
    window = FakeContextWindow(4096)
    budget = ContextBudget(context_window=window, share=0.5)

    await budget.total_tokens()
    window.length = 32768

    assert await budget.total_tokens() == 16384
    assert window.calls == 2


@pytest.mark.parametrize("share", [0.0, -0.1, 1.5])
def test_share_must_be_a_fraction_of_the_window(share: float) -> None:
    with pytest.raises(ValueError):
        ContextBudget(context_window=FakeContextWindow(4096), share=share)
