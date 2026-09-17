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

    assert "--network none" in text
    assert "--cap-drop ALL" in text
    assert "no-new-privileges" in text
    assert "/var/run/docker.sock" not in text
    assert str(Path.home()) not in text
    assert "HOME=/tmp/reproforge-home" in text
