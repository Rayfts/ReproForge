from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

T = TypeVar("T")
Predicate = Callable[[Sequence[T]], Awaitable[bool]]


async def ddmin(
    items: Sequence[T],
    predicate: Predicate[T],
    *,
    max_trials: int = 32,
) -> list[T]:
    """Reduce an ordered input while preserving the same observed failure."""

    current = list(items)
    if len(current) <= 1:
        return current
    if not await predicate(current):
        raise ValueError("initial input does not satisfy the failure predicate")

    trials = 1
    granularity = 2
    while len(current) >= 2 and trials < max_trials:
        subset_size = max(1, len(current) // granularity)
        reduced = False

        for start in range(0, len(current), subset_size):
            candidate = current[:start] + current[start + subset_size :]
            if not candidate:
                continue
            trials += 1
            if await predicate(candidate):
                current = candidate
                granularity = max(2, granularity - 1)
                reduced = True
                break
            if trials >= max_trials:
                break

        if reduced:
            continue
        if granularity >= len(current):
            break
        granularity = min(len(current), granularity * 2)

    return current
