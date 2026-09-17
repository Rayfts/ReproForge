from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from reproforge.core.models import CommandResult, CommandSpec


@dataclass(slots=True)
class StreamLine:
    stream: str
    text: str


async def run_process(
    command: CommandSpec,
    *,
    cwd: Path,
    stdin: bytes | None = None,
) -> CommandResult:
    started = datetime.now(UTC)
    proc = await asyncio.create_subprocess_exec(
        *command.argv,
        cwd=cwd,
        env=command.env or None,
        stdin=asyncio.subprocess.PIPE if stdin is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    timed_out = False
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(stdin), timeout=command.timeout_seconds)
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


async def stream_process(argv: list[str], *, cwd: Path, stdin_text: str | None = None) -> AsyncIterator[StreamLine]:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE if stdin_text is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    if stdin_text is not None and proc.stdin is not None:
        proc.stdin.write(stdin_text.encode())
        await proc.stdin.drain()
        proc.stdin.close()

    queue: asyncio.Queue[StreamLine | None] = asyncio.Queue()

    async def pump(name: str, stream: asyncio.StreamReader | None) -> None:
        if stream is None:
            await queue.put(None)
            return
        while line := await stream.readline():
            await queue.put(StreamLine(name, line.decode("utf-8", errors="replace").rstrip("\n")))
        await queue.put(None)

    tasks = [
        asyncio.create_task(pump("stdout", proc.stdout)),
        asyncio.create_task(pump("stderr", proc.stderr)),
    ]
    complete = 0
    while complete < len(tasks):
        item = await queue.get()
        if item is None:
            complete += 1
            continue
        yield item
    await asyncio.gather(*tasks)
    await proc.wait()
