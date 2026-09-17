from __future__ import annotations

import json
from collections.abc import AsyncIterator

from reproforge.core.models import CommandResult, CommandSpec
from reproforge.harnesses.base import (
    HarnessEvent,
    HarnessEventKind,
    HarnessInvocation,
    HarnessRuntime,
)
from reproforge.sandbox.docker import DockerSession


class DockerHarnessRuntime(HarnessRuntime):
    """Run a harness inside a disposable DockerSession and retain command evidence."""

    def __init__(self, session: DockerSession, *, timeout_seconds: int = 900) -> None:
        self._session = session
        self._timeout_seconds = timeout_seconds
        self._results: list[CommandResult] = []

    @property
    def results(self) -> list[CommandResult]:
        return list(self._results)

    async def stream(
        self,
        invocation: HarnessInvocation,
        *,
        harness_id: str,
    ) -> AsyncIterator[HarnessEvent]:
        if invocation.stdin_text is not None:
            raise RuntimeError("stdin-driven harness invocations are not implemented by the Docker runtime yet")

        yield HarnessEvent(
            kind=HarnessEventKind.START,
            harness_id=harness_id,
            payload={"argv": invocation.argv, "cwd": str(invocation.cwd)},
        )
        result = await self._session.run(
            CommandSpec(
                argv=invocation.argv,
                cwd=str(invocation.cwd),
                env=invocation.env,
                timeout_seconds=self._timeout_seconds,
                purpose=f"harness:{harness_id}",
            )
        )
        self._results.append(result)

        for line in result.stdout.splitlines():
            yield _stdout_event(harness_id, line, structured=invocation.structured_output)
        for line in result.stderr.splitlines():
            yield HarnessEvent(
                kind=HarnessEventKind.STDERR,
                harness_id=harness_id,
                raw=line,
                payload={},
            )

        if result.timed_out:
            yield HarnessEvent(
                kind=HarnessEventKind.ERROR,
                harness_id=harness_id,
                payload={"reason": "timeout"},
            )
        elif result.exit_code not in (0, None):
            yield HarnessEvent(
                kind=HarnessEventKind.ERROR,
                harness_id=harness_id,
                payload={"exit_code": result.exit_code},
            )

        yield HarnessEvent(
            kind=HarnessEventKind.END,
            harness_id=harness_id,
            payload={
                "exit_code": result.exit_code,
                "duration_seconds": result.duration_seconds,
                "timed_out": result.timed_out,
            },
        )

    async def cancel(self) -> None:
        await self._session.close()


def _stdout_event(harness_id: str, line: str, *, structured: bool) -> HarnessEvent:
    if not structured:
        return HarnessEvent(
            kind=HarnessEventKind.STDOUT,
            harness_id=harness_id,
            raw=line,
        )

    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return HarnessEvent(
            kind=HarnessEventKind.RAW,
            harness_id=harness_id,
            raw=line,
        )
    if not isinstance(payload, dict):
        return HarnessEvent(
            kind=HarnessEventKind.RAW,
            harness_id=harness_id,
            raw=line,
            payload={"value": payload},
        )

    event_type = str(payload.get("type") or payload.get("event") or "").lower()
    return HarnessEvent(
        kind=_kind_for_type(event_type),
        harness_id=harness_id,
        raw=line,
        payload={str(key): value for key, value in payload.items()},
    )


def _kind_for_type(event_type: str) -> HarnessEventKind:
    if "tool" in event_type:
        return HarnessEventKind.TOOL
    if "usage" in event_type or "token" in event_type:
        return HarnessEventKind.USAGE
    if "error" in event_type or "fail" in event_type:
        return HarnessEventKind.ERROR
    if "message" in event_type or "assistant" in event_type or "result" in event_type:
        return HarnessEventKind.MESSAGE
    return HarnessEventKind.RAW
