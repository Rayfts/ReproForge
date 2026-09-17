from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from reproforge.core.models import CommandResult, CommandSpec


class SandboxError(RuntimeError):
    pass


class SandboxBackend(ABC):
    @abstractmethod
    async def available(self) -> bool: ...

    @abstractmethod
    async def run(
        self,
        command: CommandSpec,
        *,
        workspace: Path,
        image: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> CommandResult: ...
