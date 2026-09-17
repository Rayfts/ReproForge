from datetime import UTC, datetime, timedelta

from reproforge.core.models import AttemptRecord, CommandResult, CommandSpec, FailureKind, RunStatus
from reproforge.validation.oracles import classify_attempts, inspect_command


def _failure(stderr: str, *, stdout: str = "", exit_code: int = 1, argv: list[str] | None = None) -> CommandResult:
    start = datetime.now(UTC)
    return CommandResult(
        command=CommandSpec(argv=argv or ["test-command"], purpose="test"),
        exit_code=exit_code,
        stdout=stdout,
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


def test_node_duration_jitter_does_not_change_fingerprint() -> None:
    first = """TAP version 13
not ok 1 - preserves display name
  duration_ms: 4.396879
  error: Expected values to be strictly equal
  name: AssertionError
# duration_ms 117.475549
"""
    second = first.replace("4.396879", "7.225162").replace("117.475549", "114.155812")

    first_signal = inspect_command(_failure("", stdout=first, argv=["npm", "test"]), command_index=0)[0]
    second_signal = inspect_command(_failure("", stdout=second, argv=["npm", "test"]), command_index=0)[0]

    assert first_signal.fingerprint == second_signal.fingerprint


def test_rust_warm_cache_build_noise_does_not_change_fingerprint() -> None:
    cold = """thread 'tests::empty_input_is_supported' panicked at src/lib.rs:2:5:
index out of bounds: the len is 0 but the index is 0
   Compiling fixture v0.1.0 (/workspace)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.22s
error: test failed, to rerun pass `--lib`
"""
    warm = """thread 'tests::empty_input_is_supported' panicked at src/lib.rs:2:5:
index out of bounds: the len is 0 but the index is 0
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.01s
error: test failed, to rerun pass `--lib`
"""

    first_signal = inspect_command(_failure(cold, exit_code=101, argv=["cargo", "test"]), command_index=0)[0]
    second_signal = inspect_command(_failure(warm, exit_code=101, argv=["cargo", "test"]), command_index=0)[0]

    assert first_signal.fingerprint == second_signal.fingerprint
