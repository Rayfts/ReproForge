from __future__ import annotations

import asyncio
import platform
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from reproforge.core.config import SandboxConfig
from reproforge.core.models import CommandResult, CommandSpec
from reproforge.sandbox.base import SandboxBackend, SandboxError


class DockerSession:
    """Long-lived disposable container for one reproduction run."""

    def __init__(
        self,
        backend: DockerSandbox,
        *,
        workspace: Path,
        image: str,
        environment: dict[str, str],
    ) -> None:
        self.backend = backend
        self.workspace = workspace.resolve()
        self.image = image
        self.environment = environment
        self.name = f"reproforge-{uuid.uuid4().hex[:12]}"
        self._started = False

    async def __aenter__(self) -> DockerSession:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        if self._started:
            return
        argv = self.backend._container_argv(
            workspace=self.workspace,
            image=self.image,
            environment=self.environment,
            name=self.name,
        )
        argv.extend(["sh", "-c", "while :; do sleep 3600; done"])
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise SandboxError(
                "failed to start Docker sandbox: "
                + stderr.decode("utf-8", errors="replace")[:2000]
            )
        if not stdout.strip():
            raise SandboxError("Docker did not return a container id")
        self._started = True

    async def run(self, command: CommandSpec) -> CommandResult:
        if not self._started:
            raise SandboxError("Docker session has not been started")

        argv = ["docker", "exec", "--workdir", command.cwd]
        env = dict(self.environment)
        env.update(command.env)
        for key, value in sorted(env.items()):
            self.backend._validate_env(key, value)
            argv.extend(["--env", f"{key}={value}"])
        argv.extend([self.name, *command.argv])
        return await _capture(argv, command)

    async def close(self) -> None:
        if not self._started:
            return
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "rm",
            "-f",
            self.name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        self._started = False


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

    async def open_session(
        self,
        *,
        workspace: Path,
        image: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> DockerSession:
        if not await self.available():
            raise SandboxError(
                "Docker is not available; ReproForge will not execute untrusted code on the host"
            )
        selected_image = image or self.config.image
        if selected_image is None:
            raise SandboxError("no Docker image was selected for this project")
        return DockerSession(
            self,
            workspace=workspace,
            image=selected_image,
            environment=dict(environment or {}),
        )

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
        return await _capture(argv, command)

    def _container_argv(
        self,
        *,
        workspace: Path,
        image: str,
        environment: dict[str, str],
        name: str,
    ) -> list[str]:
        limits = self.config.limits
        argv = [
            "docker",
            "run",
            "--detach",
            "--name",
            name,
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
            "/workspace",
            "--mount",
            f"type=bind,source={workspace},target=/workspace",
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
            self._validate_env(key, value)
            argv.extend(["--env", f"{key}={value}"])
        argv.append(image)
        return argv

    def _docker_argv(
        self,
        command: CommandSpec,
        workspace: Path,
        image: str,
        environment: dict[str, str],
    ) -> list[str]:
        argv = self._container_argv(
            workspace=workspace,
            image=image,
            environment=environment,
            name=f"reproforge-once-{uuid.uuid4().hex[:8]}",
        )
        name_index = argv.index("--name")
        del argv[name_index : name_index + 2]
        argv.insert(2, "--rm")
        workdir_index = argv.index("--workdir")
        argv[workdir_index + 1] = command.cwd
        argv.extend(command.argv)
        return argv

    @staticmethod
    def _validate_env(key: str, value: str) -> None:
        if "\x00" in key or "\x00" in value:
            raise SandboxError("environment contains a NUL byte")
        if not key or "=" in key:
            raise SandboxError(f"invalid environment key: {key!r}")

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


async def _capture(argv: list[str], command: CommandSpec) -> CommandResult:
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
