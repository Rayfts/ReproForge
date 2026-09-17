from datetime import UTC, datetime, timedelta

from reproforge.core.models import AttemptRecord, CommandResult, CommandSpec, FailureKind, RunStatus
from reproforge.validation.oracles import classify_attempts, inspect_command


def _failure(stderr: str, *, exit_code: int = 1) -> CommandResult:
    start = datetime.now(UTC)
    return CommandResult(
        command=CommandSpec(argv=["test-command"], purpose="test"),
        exit_code=exit_code,
        stdout="",
        stderr=stderr,
        started_at=start,
        finished_at=start + timedelta(milliseconds=20),
        duration_seconds=0.02,
    )


def test_panic_is_observed_from_process_evidence() -> None:
    signals = inspect_command(_failure("thread 'main' panicked at src/lib.rs:2"), command_index=0)
    assert len(signals) == 1
    assert signals[0].kind == FailureKind.PANIC
    assert signals[0].fingerprint


def test_identical_observed_failures_are_deterministic() -> None:
    first_signal = inspect_command(_failure("AssertionError: expected 5, got 4"), command_index=0)[0]
    second_signal = inspect_command(_failure("AssertionError: expected 5, got 4"), command_index=0)[0]
    attempts = [
        AttemptRecord(attempt=1, commands=[], signals=[first_signal], reproduced=True),
        AttemptRecord(attempt=2, commands=[], signals=[second_signal], reproduced=True),
    ]

    status, rate, deterministic, confidence, primary = classify_attempts(
        attempts,
        flake_threshold=0.34,
    )

    assert status == RunStatus.REPRODUCED
    assert rate == 1.0
    assert deterministic is True
    assert confidence >= 0.9
    assert primary is not None
