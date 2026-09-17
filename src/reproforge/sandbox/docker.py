from __future__ import annotations

import asyncio
import platform
import shutil
from datetime import UTC, datetime
from pathlib import Path

from reproforge.core.config import SandboxConfig
from reproforge.core.models import CommandResult, CommandSpec
from reproforge.sandbox.base import SandboxBackend, SandboxError


class DockerSandbox(SandboxBackend):
    def __init__(self, config: SandboxConfig) -> None:
        self.config = config

    async def available(self) -> bool:
        if shutil.which("docker") is None:
            return False
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "info",
            "--format",
            "{{.ServerVersion}}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return await proc.wait() == 0

    async def run(
        self,
        command: CommandSpec,
        *,
        workspace: Path,
        image: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> CommandResult:
        if not await self.available():
            raise SandboxError(
                "Docker is not available; ReproForge will not execute untrusted code on the host"
            )
        workspace = workspace.resolve()
        selected_image = image or self.config.image
        if selected_image is None:
            raise SandboxError("no Docker image was selected for this project")
        env = dict(environment or {})
        env.update(command.env)
        argv = self._docker_argv(command, workspace, selected_image, env)
        started = datetime.now(UTC)
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timed_out = False
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=command.timeout_seconds
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

    def _docker_argv(
        self,
        command: CommandSpec,
        workspace: Path,
        image: str,
        environment: dict[str, str],
    ) -> list[str]:
        limits = self.config.limits
        argv = [
            "docker",
            "run",
            "--rm",
            "--init",
            "--network",
            self.config.network,
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(limits.pids),
            "--memory",
            f"{limits.memory_mb}m",
            "--cpus",
            str(limits.cpus),
            "--workdir",
            command.cwd,
            "--mount",
            f"type=bind,source={workspace},target=/workspace,rw",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,exec,size=512m",
            "--env",
            "HOME=/tmp/reproforge-home",
            "--env",
            "CI=1",
        ]
        if self.config.read_only_root:
            argv.append("--read-only")
        for key, value in sorted(environment.items()):
            if "\x00" in key or "\x00" in value:
                raise SandboxError("environment contains a NUL byte")
            argv.extend(["--env", f"{key}={value}"])
        argv.append(image)
        argv.extend(command.argv)
        return argv

    def environment_summary(self) -> dict[str, object]:
        return {
            "backend": "docker",
            "image": self.config.image,
            "platform": platform.platform(),
            "network_policy": self.config.network,
            "cpu_limit": self.config.limits.cpus,
            "memory_limit_mb": self.config.limits.memory_mb,
            "pids_limit": self.config.limits.pids,
            "docker_socket_exposed": False,
            "host_home_exposed": False,
            "host_environment_inherited": False,
        }
