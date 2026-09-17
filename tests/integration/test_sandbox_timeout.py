from pathlib import Path

import pytest

from reproforge.core.config import SandboxConfig
from reproforge.core.models import CommandSpec
from reproforge.sandbox.docker import DockerSandbox


@pytest.mark.integration
@pytest.mark.asyncio
async def test_timed_out_command_does_not_poison_session(tmp_path: Path) -> None:
    sandbox = DockerSandbox(SandboxConfig(image="python:3.12-slim"))
    if not await sandbox.available():
        pytest.skip("Docker is not available")

    session = await sandbox.open_session(workspace=tmp_path)
    async with session:
        timed_out = await session.run(
            CommandSpec(
                argv=["python", "-c", "import time; time.sleep(10)"],
                timeout_seconds=1,
                purpose="timeout-test",
            )
        )
        after_restart = await session.run(
            CommandSpec(
                argv=["python", "-c", "print('healthy')"],
                purpose="post-timeout-test",
            )
        )

    assert timed_out.timed_out is True
    assert after_restart.exit_code == 0
    assert after_restart.stdout.strip() == "healthy"
