from __future__ import annotations

from reproforge.core.models import CommandResult, ReproductionReport


def render_issue_comment(report: ReproductionReport) -> str:
    lines = [
        "### ReproForge evidence",
        "",
        f"**Status:** `{report.status.value}`  ",
        f"**Confidence:** `{report.confidence:.2f}`  ",
        f"**Reproduction rate:** `{report.reproduction_rate:.0%}`  ",
        f"**Deterministic:** `{'yes' if report.deterministic else 'no'}`",
    ]

    failing = _primary_command(report)
    if failing is not None:
        lines.extend(
            [
                "",
                "**Observed failing command**",
                f"`{' '.join(failing.command.argv)}` — "
                f"{'timed out' if failing.timed_out else f'exit {failing.exit_code}'}",
            ]
        )

    environment = report.environment
    environment_bits = [f"backend={environment.backend}"]
    if environment.image:
        environment_bits.append(f"image={environment.image}")
    if environment.revision:
        environment_bits.append(f"revision={environment.revision[:12]}")
    lines.extend(["", f"**Environment:** `{', '.join(environment_bits)}`"])

    if report.primary_signal is not None:
        lines.append(f"**Observed signal:** `{report.primary_signal.kind.value}` — {report.primary_signal.summary}")
    if report.generated_regression_test:
        lines.append(f"**Proposed regression test:** {report.generated_regression_test}")
    if report.caveats:
        lines.extend(["", "**Caveats**"])
        lines.extend(f"- {caveat}" for caveat in report.caveats[:3])

    lines.extend(
        [
            "",
            f"Run ID: `{report.run_id}`. Full machine-readable evidence is stored in the ReproForge artifact bundle.",
        ]
    )
    return "\n".join(lines) + "\n"


def _primary_command(report: ReproductionReport) -> CommandResult | None:
    primary = report.primary_signal
    if primary is None or primary.command_index is None:
        return None
    for attempt in report.attempts:
        if not attempt.reproduced:
            continue
        if primary.command_index < len(attempt.commands):
            return attempt.commands[primary.command_index]
    return None
