import pytest

from reproforge.minimization.ddmin import ddmin


@pytest.mark.asyncio
async def test_ddmin_reduces_while_preserving_predicate() -> None:
    async def fails(candidate) -> bool:
        return 3 in candidate

    result = await ddmin([1, 2, 3, 4, 5], fails, max_trials=32)
    assert result == [3]
