from pathlib import Path

from reproforge.core.models import (
    EnvironmentSnapshot,
    ReproductionReport,
    ReproductionRequest,
    RunStatus,
    utcnow,
)
from reproforge.reports.writer import write_report_bundle


def test_report_bundle_has_stable_required_files(tmp_path: Path) -> None:
    now = utcnow()
    report = ReproductionReport(
        run_id="test-run",
        status=RunStatus.NOT_REPRODUCED,
        confidence=0.65,
        summary="No observed failure.",
        request=ReproductionRequest(source="local", local_path=tmp_path),
        started_at=now,
        finished_at=now,
        environment=EnvironmentSnapshot(
            backend="docker",
            platform="test",
            network_policy="none",
        ),
        reproduction_rate=0.0,
    )

    output = write_report_bundle(tmp_path, report)

    for name in (
        "report.json",
        "report.md",
        "environment.json",
        "attempts.jsonl",
        "commands.jsonl",
    ):
        assert (output / name).is_file()
    assert (output / "report.json").read_text().count('"schema_version": "1.0"') == 1
