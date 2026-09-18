from __future__ import annotations

import asyncio
import shutil
from collections.abc import AsyncIterator, Callable
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import Field

from reproforge.core.models import StrictModel


class IntegrationMode(StrEnum):
    CLI = "direct-cli"
    HEADLESS = "headless"
    JSON_STREAM = "structured-json-stream"
    RPC = "rpc"
    TRANSCRIPT_IMPORT = "transcript-import"
    EXTENSION = "extension"
    ARCHIVAL = "archival"


class HarnessEventKind(StrEnum):
    START = "start"
    STDOUT = "stdout"
    STDERR = "stderr"
    TOOL = "tool"
    FILE_CHANGE = "file-change"
    MESSAGE = "message"
    USAGE = "usage"
    ERROR = "error"
    END = "end"
    RAW = "raw"


class CapabilityReport(StrictModel):
    id: str
    display_name: str
    repository: str
    integration_modes: list[IntegrationMode]
    installed: bool = False
    executable: str | None = None
    version: str | None = None
    launchable: bool = True
    structured_output: bool = False
    supports_resume: bool = False
    supports_mcp: bool = False
    limitations: list[str] = Field(default_factory=list)
    evidence_urls: list[str] = Field(default_factory=list)


class HarnessEvent(StrictModel):
    kind: HarnessEventKind
    harness_id: str
    payload: dict[str, object] = Field(default_factory=dict)
    raw: str | None = None


class HarnessRunRequest(StrictModel):
    prompt: str
    cwd: Path
    env: dict[str, str] = Field(default_factory=dict)
    model: str | None = None
    session_id: str | None = None


class HarnessInvocation(StrictModel):
    argv: list[str]
    cwd: Path
    env: dict[str, str] = Field(default_factory=dict)
    stdin_text: str | None = None
    structured_output: bool = False


class HarnessRuntime(Protocol):
    """Execution boundary supplied by ReproForge's sandbox layer."""

    def stream(
        self,
        invocation: HarnessInvocation,
        *,
        harness_id: str,
    ) -> AsyncIterator[HarnessEvent]: ...

    async def cancel(self) -> None: ...


class HarnessAdapter(Protocol):
    id: str

    async def detect(self) -> CapabilityReport: ...

    async def prepare(self, request: HarnessRunRequest) -> None: ...

    def build_invocation(self, request: HarnessRunRequest) -> HarnessInvocation: ...

    def run(self, request: HarnessRunRequest) -> AsyncIterator[HarnessEvent]: ...

    async def cancel(self) -> None: ...


InvocationBuilder = Callable[[HarnessRunRequest], HarnessInvocation]


async def probe_version(executable: str) -> tuple[bool, str | None]:
    path = shutil.which(executable)
    if path is None:
        return False, None

    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            path,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
    except TimeoutError:
        if process is not None:
            process.kill()
            await process.communicate()
        return True, None
    except OSError:
        return True, None

    text = (stdout or stderr).decode(errors="replace").strip()
    return True, text.splitlines()[0] if text else None


class CliHarnessAdapter:
    """CLI adapter that refuses to execute without an injected sandbox runtime."""

    def __init__(
        self,
        *,
        capability: CapabilityReport,
        executable: str,
        invocation_builder: InvocationBuilder,
        runtime: HarnessRuntime | None = None,
    ) -> None:
        self.id = capability.id
        self._capability = capability
        self._executable = executable
        self._invocation_builder = invocation_builder
        self._runtime = runtime

    async def detect(self) -> CapabilityReport:
        installed, version = await probe_version(self._executable)
        return self._capability.model_copy(
            update={
                "installed": installed,
                "executable": shutil.which(self._executable),
                "version": version,
            }
        )

    async def prepare(self, request: HarnessRunRequest) -> None:
        request.cwd.resolve(strict=True)

    def build_invocation(self, request: HarnessRunRequest) -> HarnessInvocation:
        return self._invocation_builder(request)

    async def run(self, request: HarnessRunRequest) -> AsyncIterator[HarnessEvent]:
        if self._runtime is None:
            raise RuntimeError(f"{self.id} requires an injected sandbox HarnessRuntime; host execution is intentionally disabled")
        invocation = self.build_invocation(request)
        async for event in self._runtime.stream(invocation, harness_id=self.id):
            yield event

    async def cancel(self) -> None:
        if self._runtime is not None:
            await self._runtime.cancel()


class ArchivalHarnessAdapter:
    def __init__(self, capability: CapabilityReport) -> None:
        self.id = capability.id
        self._capability = capability

    async def detect(self) -> CapabilityReport:
        return self._capability

    async def prepare(self, request: HarnessRunRequest) -> None:
        del request

    def build_invocation(self, request: HarnessRunRequest) -> HarnessInvocation:
        del request
        raise RuntimeError(f"{self.id} has no current supported headless launcher; historical artifacts must be imported explicitly")

    async def run(self, request: HarnessRunRequest) -> AsyncIterator[HarnessEvent]:
        del request
        if self._capability.launchable:
            yield HarnessEvent(
                kind=HarnessEventKind.ERROR,
                harness_id=self.id,
                payload={"reason": "archival-adapter-misconfigured"},
            )
        raise RuntimeError(f"{self.id} is archival-only because the official project is shut down")

    async def cancel(self) -> None:
        return None
