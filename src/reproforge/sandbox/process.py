from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from reproforge.core.models import CommandResult, CommandSpec


async def capture_command(argv: list[str], command: CommandSpec) -> CommandResult:
    started = datetime.now(UTC)
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    timed_out = False
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(),
            timeout=command.timeout_seconds,
        )
    except TimeoutError:
        timed_out = True
        proc.kill()
        stdout_b, stderr_b = await proc.communicate()
    finished = datetime.now(UTC)
    return CommandResult(
        command=command,
        exit_code=proc.returncode,
        stdout=stdout_b.decode("utf-8", errors="replace"),
        stderr=stderr_b.decode("utf-8", errors="replace"),
        started_at=started,
        finished_at=finished,
        timed_out=timed_out,
        duration_seconds=(finished - started).total_seconds(),
    )
