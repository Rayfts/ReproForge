from pathlib import Path

from reproforge.cli.runtime import archive_run
from reproforge.core.models import (
    EnvironmentSnapshot,
    ReproductionReport,
    ReproductionRequest,
    RunStatus,
    utcnow,
)


def test_archive_fallback_does_not_write_to_workspace(tmp_path: Path, monkeypatch) -> None:
    control_home = tmp_path / "control"
    workspace = tmp_path / "sensitive-workspace"
    workspace.mkdir()
    monkeypatch.setenv("REPROFORGE_HOME", str(control_home))

    now = utcnow()
    report = ReproductionReport(
        run_id="blocked-run",
        status=RunStatus.INFRASTRUCTURE_FAILURE,
        confidence=0.0,
        summary="Workspace blocked by policy.",
        request=ReproductionRequest(source="local", local_path=workspace),
        started_at=now,
        finished_at=now,
        environment=EnvironmentSnapshot(
            backend="docker",
            platform="test",
            network_policy="none",
        ),
        reproduction_rate=0.0,
    )

    archive = archive_run(workspace, report)

    assert (archive / "report.json").is_file()
    assert (archive / "environment.json").is_file()
    assert (archive / "metadata.json").is_file()
    assert not (workspace / ".reproforge").exists()
    assert not (control_home / "staging" / report.run_id).exists()
