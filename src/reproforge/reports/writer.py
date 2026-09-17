from __future__ import annotations

import json
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
        for result in report.setup_commands:
            lines.append(_command_line(result))
    else:
        lines.append("- No setup commands were required or detected.")

    lines.extend(["", "## Baseline", ""])
    if report.baseline_commands:
        for result in report.baseline_commands:
            lines.append(_command_line(result))
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
    lines: list[str] = []
    for phase, commands in (
        ("setup", report.setup_commands),
        ("baseline", report.baseline_commands),
    ):
        for command in commands:
            lines.append(
                _jsonl_command(
                    command,
                    {"phase": phase},
                    secret_values,
                )
            )
    for attempt in report.attempts:
        for command in attempt.commands:
            lines.append(
                _jsonl_command(
                    command,
                    {"phase": "attempt", "attempt": attempt.attempt},
                    secret_values,
                )
            )
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _jsonl_command(
    command: CommandResult,
    metadata: dict[str, object],
    secret_values: tuple[str, ...],
) -> str:
    payload = {**metadata, **command.model_dump(mode="json")}
    return redact(json.dumps(payload, sort_keys=True), secret_values=secret_values)
