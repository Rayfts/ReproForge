from __future__ import annotations

from reproforge.harnesses.base import (
    ArchivalHarnessAdapter,
    CapabilityReport,
    CliHarnessAdapter,
    HarnessAdapter,
    HarnessRuntime,
)
from reproforge.harnesses.catalog import CAPABILITIES


def harness_ids() -> tuple[str, ...]:
    return tuple(CAPABILITIES)


def create_adapter(
    harness_id: str,
    *,
    runtime: HarnessRuntime | None = None,
) -> HarnessAdapter:
    try:
        capability, executable, builder = CAPABILITIES[harness_id]
    except KeyError as exc:
        known = ", ".join(harness_ids())
        raise ValueError(f"unknown harness {harness_id!r}; expected one of: {known}") from exc

    if executable is None or builder is None:
        return ArchivalHarnessAdapter(capability)

    return CliHarnessAdapter(
        capability=capability,
        executable=executable,
        invocation_builder=builder,
        runtime=runtime,
    )


def capability_catalog() -> list[CapabilityReport]:
    return [entry[0].model_copy(deep=True) for entry in CAPABILITIES.values()]
