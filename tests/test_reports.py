import json
from pathlib import Path

from reproforge.core.models import (
    AttemptRecord,
    CommandResult,
    CommandSpec,
    EnvironmentSnapshot,
    ReproductionReport,
    ReproductionRequest,
    RunStatus,
    utcnow,
)
from reproforge.reports.writer import write_report_bundle


def test_report_bundle_has_stable_required_files(tmp_path: Path) -> None:
    now = utcnow()
    harness_result = CommandResult(
        command=CommandSpec(argv=["codex", "exec", "--json", "reproduce"], purpose="harness:codex"),
        exit_code=0,
        stdout='{"type":"result","text":"investigated"}\n',
        started_at=now,
        finished_at=now,
        duration_seconds=0.0,
    )
    result = CommandResult(
        command=CommandSpec(argv=["pytest", "-q"], purpose="test"),
        exit_code=1,
        stdout="one failed\n",
        stderr="AssertionError: expected 2, got 1\n",
        started_at=now,
        finished_at=now,
        duration_seconds=0.0,
    )
    report = ReproductionReport(
        run_id="test-run",
        status=RunStatus.REPRODUCED,
        confidence=0.95,
        summary="Observed deterministic failure.",
        request=ReproductionRequest(source="local", local_path=tmp_path),
        started_at=now,
        finished_at=now,
        environment=EnvironmentSnapshot(
            backend="docker",
            platform="test",
            network_policy="none",
        ),
        harness_id="codex",
        harness_commands=[harness_result],
        attempts=[AttemptRecord(attempt=1, commands=[result], reproduced=True)],
        reproduction_rate=1.0,
        deterministic=True,
        baseline_ok=True,
        minimized_reproduction="pytest -q",
        generated_regression_test="tests/test_regression.py",
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
    commands = [json.loads(line) for line in (output / "commands.jsonl").read_text().splitlines()]
    assert any(item["phase"] == "harness" and item["command"]["purpose"] == "harness:codex" for item in commands)
    assert (output / "reproduction" / "commands.json").is_file()
    assert (output / "reproduction" / "minimized.txt").read_text().strip() == "pytest -q"
    assert (output / "regression-test" / "proposal.md").read_text().strip() == "tests/test_regression.py"
    assert any((output / "logs").glob("*.stdout.log"))
    assert any((output / "logs").glob("*.stderr.log"))
