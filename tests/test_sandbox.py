from pathlib import Path

from reproforge.core.config import SandboxConfig
from reproforge.core.models import CommandSpec
from reproforge.sandbox.docker import DockerSandbox


def test_docker_argv_keeps_host_credentials_out(tmp_path: Path) -> None:
    sandbox = DockerSandbox(SandboxConfig(image="python:3.12-slim"))
    argv = sandbox._docker_argv(
        CommandSpec(argv=["python", "-V"]),
        tmp_path,
        "python:3.12-slim",
        {},
    )
    text = " ".join(argv)
    mounts = [argv[index + 1] for index, value in enumerate(argv) if value == "--mount"]

    assert "--network none" in text
    assert "--cap-drop ALL" in text
    assert "no-new-privileges" in text
    assert mounts == [f"type=bind,source={tmp_path.resolve()},target=/workspace"]
    assert all("/var/run/docker.sock" not in mount for mount in mounts)
    assert all(".ssh" not in mount for mount in mounts)
    assert all(".aws" not in mount for mount in mounts)
    assert all(".config/gh" not in mount for mount in mounts)
    assert "HOME=/tmp/reproforge-home" in text
