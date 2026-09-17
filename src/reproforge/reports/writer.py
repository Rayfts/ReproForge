from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from reproforge.core.models import AttemptRecord, CommandResult, ReproductionReport
from reproforge.security.redaction import redact

_REQUIRED_DIRS = (
    "logs",
    "patches",
    "artifacts",
    "reproduction",
    "regression-test",
)


def write_report_bundle(
    root: Path,
    report: ReproductionReport,
    *,
    secret_values: tuple[str, ...] = (),
) -> Path:
    output = root / ".reproforge"
    output.mkdir(parents=True, exist_ok=True)
    for name in _REQUIRED_DIRS:
        (output / name).mkdir(exist_ok=True)

    _write_json(output / "report.json", report.model_dump(mode="json"), secret_values)
    _write_json(output / "environment.json", report.environment.model_dump(mode="json"), secret_values)
    _write_attempts(output / "attempts.jsonl", report.attempts, secret_values)
    _write_commands(output / "commands.jsonl", report, secret_values)
    _write_logs(output / "logs", report, secret_values)
    _write_reproduction(output / "reproduction", report, secret_values)
    _write_regression_test(output / "regression-test", report, secret_values)
    (output / "report.md").write_text(
        redact(render_markdown(report), secret_values=secret_values),
        encoding="utf-8",
    )
    return output


def render_markdown(report: ReproductionReport) -> str:
    primary = report.primary_signal
    lines = [
        "# ReproForge report",
        "",
        f"- **Run:** `{report.run_id}`",
        f"- **Status:** `{report.status.value}`",
        f"- **Confidence:** `{report.confidence:.2f}`",
        f"- **Reproduction rate:** `{report.reproduction_rate:.0%}`",
        f"- **Deterministic:** `{'yes' if report.deterministic else 'no'}`",
        f"- **Baseline healthy:** `{'yes' if report.baseline_ok else 'no'}`",
    ]
    if report.harness_id:
        lines.append(f"- **Harness:** `{report.harness_id}`")
    lines.extend(["", "## Summary", "", report.summary])

    lines.extend(["", "## Environment setup", ""])
    if report.setup_commands:
        lines.extend(_command_line(result) for result in report.setup_commands)
    else:
        lines.append("- No setup commands were required or detected.")

    lines.extend(["", "## Baseline", ""])
    if report.baseline_commands:
        lines.extend(_command_line(result) for result in report.baseline_commands)
    else:
        lines.append("- No separate baseline build/check command was detected.")

    if primary:
        lines.extend(
            [
                "",
                "## Primary observed failure",
                "",
                f"- Kind: `{primary.kind.value}`",
                f"- Summary: {primary.summary}",
                f"- Fingerprint: `{primary.fingerprint or 'n/a'}`",
            ]
        )

    lines.extend(["", "## Attempts", ""])
    for attempt in report.attempts:
        lines.append(
            f"- Attempt {attempt.attempt}: "
            f"{'reproduced' if attempt.reproduced else 'not reproduced'}; "
            f"{len(attempt.commands)} command(s), {len(attempt.signals)} observed signal(s)"
        )

    if report.generated_regression_test:
        lines.extend(["", "## Proposed regression test", "", report.generated_regression_test])
    if report.minimized_reproduction:
        lines.extend(["", "## Minimized reproduction", "", report.minimized_reproduction])
    if report.caveats:
        lines.extend(["", "## Caveats", ""])
        lines.extend(f"- {item}" for item in report.caveats)

    return "\n".join(lines).rstrip() + "\n"


def _command_line(result: CommandResult) -> str:
    command = " ".join(result.command.argv)
    suffix = "timed out" if result.timed_out else f"exit {result.exit_code}"
    return f"- `{command}` — {suffix} ({result.duration_seconds:.2f}s)"


def _write_json(path: Path, payload: object, secret_values: tuple[str, ...]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True)
    path.write_text(redact(text, secret_values=secret_values) + "\n", encoding="utf-8")


def _write_attempts(
    path: Path,
    attempts: list[AttemptRecord],
    secret_values: tuple[str, ...],
) -> None:
    lines = [
        redact(
            json.dumps(attempt.model_dump(mode="json"), sort_keys=True),
            secret_values=secret_values,
        )
        for attempt in attempts
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_commands(
    path: Path,
    report: ReproductionReport,
    secret_values: tuple[str, ...],
) -> None:
    lines = [
        _jsonl_command(command, metadata, secret_values)
        for metadata, command in _iter_commands(report)
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_logs(
    directory: Path,
    report: ReproductionReport,
    secret_values: tuple[str, ...],
) -> None:
    for index, (metadata, result) in enumerate(_iter_commands(report), start=1):
        phase = str(metadata["phase"])
        attempt = metadata.get("attempt")
        prefix = f"{index:03d}-{phase}"
        if attempt is not None:
            prefix += f"-attempt-{attempt}"
        for stream, text in (("stdout", result.stdout), ("stderr", result.stderr)):
            if not text:
                continue
            (directory / f"{prefix}.{stream}.log").write_text(
                redact(text, secret_values=secret_values),
                encoding="utf-8",
            )


def _write_reproduction(
    directory: Path,
    report: ReproductionReport,
    secret_values: tuple[str, ...],
) -> None:
    attempts = report.attempts
    fallback = attempts[0] if attempts else None
    source_attempt = next((attempt for attempt in attempts if attempt.reproduced), fallback)
    commands = (
        []
        if source_attempt is None
        else [result.command.model_dump(mode="json") for result in source_attempt.commands]
    )
    _write_json(directory / "commands.json", commands, secret_values)
    if report.minimized_reproduction:
        (directory / "minimized.txt").write_text(
            redact(report.minimized_reproduction, secret_values=secret_values) + "\n",
            encoding="utf-8",
        )


def _write_regression_test(
    directory: Path,
    report: ReproductionReport,
    secret_values: tuple[str, ...],
) -> None:
    if not report.generated_regression_test:
        return
    (directory / "proposal.md").write_text(
        redact(report.generated_regression_test, secret_values=secret_values) + "\n",
        encoding="utf-8",
    )


def _iter_commands(
    report: ReproductionReport,
) -> Iterator[tuple[dict[str, object], CommandResult]]:
    for phase, commands in (
        ("setup", report.setup_commands),
        ("baseline", report.baseline_commands),
    ):
        for command in commands:
            yield {"phase": phase}, command
    for attempt in report.attempts:
        for command in attempt.commands:
            yield {"phase": "attempt", "attempt": attempt.attempt}, command


def _jsonl_command(
    command: CommandResult,
    metadata: dict[str, object],
    secret_values: tuple[str, ...],
) -> str:
    payload = {**metadata, **command.model_dump(mode="json")}
    return redact(json.dumps(payload, sort_keys=True), secret_values=secret_values)
