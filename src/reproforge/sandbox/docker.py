from __future__ import annotations

import asyncio
import os
import platform
import shutil
import uuid
from pathlib import Path
from types import TracebackType

from reproforge.core.config import SandboxConfig
from reproforge.core.models import CommandResult, CommandSpec
from reproforge.sandbox.base import SandboxBackend, SandboxError
from reproforge.sandbox.process import capture_command


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

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb
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
        argv.extend(["sh", "-c", 'mkdir -p "$HOME" && while :; do sleep 3600; done'])
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise SandboxError("failed to start Docker sandbox: " + stderr.decode("utf-8", errors="replace")[:2000])
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
        result = await capture_command(argv, command)
        if result.timed_out:
            await self._restart_after_timeout()
        return result

    async def reset_runtime(self) -> None:
        """Restart the container while retaining its writable image layer.

        Restarting clears background processes and recreates tmpfs-backed HOME,
        while preserving setup work installed into the container layer. The bind
        mounted workspace is restored separately by the reproduction engine.
        """

        if not self._started:
            raise SandboxError("Docker session has not been started")
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "restart",
            self.name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            await self.close()
            raise SandboxError("failed to reset Docker sandbox: " + stderr.decode(errors="replace")[:1000])

    async def _restart_after_timeout(self) -> None:
        kill = await asyncio.create_subprocess_exec(
            "docker",
            "kill",
            self.name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, kill_stderr = await kill.communicate()
        if kill.returncode != 0:
            await self.close()
            raise SandboxError("failed to stop timed-out sandbox: " + kill_stderr.decode(errors="replace")[:1000])

        restart = await asyncio.create_subprocess_exec(
            "docker",
            "start",
            self.name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, restart_stderr = await restart.communicate()
        if restart.returncode != 0:
            await self.close()
            raise SandboxError("failed to restart sandbox after timeout: " + restart_stderr.decode(errors="replace")[:1000])

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
            raise SandboxError("Docker is not available; ReproForge will not execute untrusted code on the host")
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
        session = await self.open_session(
            workspace=workspace.resolve(),
            image=image,
            environment=environment,
        )
        async with session:
            return await session.run(command)

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
        host_user = _host_user()
        if host_user is not None:
            argv.extend(["--user", host_user])
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


def _host_user() -> str | None:
    """Match bind-mount ownership on POSIX without exposing host identity data."""

    if os.name == "nt":
        return None
    return f"{os.getuid()}:{os.getgid()}"
