from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from reproforge import __version__
from reproforge.cli.operations import resume_run, run_doctor, run_issue, run_local
from reproforge.cli.runtime import (
    console,
    die,
    export_run,
    load_archived_run,
    print_report,
    run_async,
    run_async_result,
)
from reproforge.harnesses import capability_catalog, create_adapter, harness_ids

app = typer.Typer(
    name="reproforge",
    no_args_is_help=True,
    help="Turn bug reports into reproducible evidence.",
)


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", help="Print the ReproForge version and exit."),
) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit()


@app.command("issue")
def issue_command(
    url: str = typer.Argument(..., help="GitHub issue URL."),
    harness: str | None = typer.Option(None, "--harness", help="Coding-agent harness id."),
    revision: str | None = typer.Option(None, "--revision", help="Git revision to reproduce."),
    image: str | None = typer.Option(None, "--image", help="Docker image for project execution."),
    harness_image: str | None = typer.Option(
        None,
        "--harness-image",
        help="Docker image containing the selected harness binary.",
    ),
    config: Path | None = typer.Option(None, "--config", exists=True, dir_okay=False),
) -> None:
    """Reproduce a GitHub issue inside a persistent disposable workspace."""

    run_async(
        run_issue(
            url=url,
            harness=harness,
            revision=revision,
            image=image,
            harness_image=harness_image,
            config_path=config,
        )
    )


@app.command("local")
def local_command(
    path: Path = typer.Argument(Path("."), exists=True, file_okay=False, resolve_path=True),
    harness: str | None = typer.Option(None, "--harness", help="Coding-agent harness id."),
    image: str | None = typer.Option(None, "--image", help="Docker image for project execution."),
    harness_image: str | None = typer.Option(None, "--harness-image"),
    config: Path | None = typer.Option(None, "--config", exists=True, dir_okay=False),
) -> None:
    """Investigate a local repository without executing project code on the host."""

    run_async(
        run_local(
            path=path,
            harness=harness,
            image=image,
            harness_image=harness_image,
            config_path=config,
        )
    )


@app.command("resume")
def resume_command(
    run_id: str = typer.Argument(..., help="Previously archived ReproForge run id."),
    harness: str | None = typer.Option(None, "--harness", help="Override the prior harness."),
    image: str | None = typer.Option(None, "--image", help="Override the Docker image."),
) -> None:
    """Continue from a stored workspace using the prior request and current repository state."""

    run_async(resume_run(run_id=run_id, harness=harness, image=image))


@app.command("inspect")
def inspect_command(
    run_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json", help="Print the full report JSON."),
) -> None:
    """Inspect an archived run without executing code."""

    report, _ = load_archived_run(run_id)
    if as_json:
        console.print_json(report.model_dump_json(indent=2))
        return
    print_report(report)


@app.command("export")
def export_command(
    run_id: str = typer.Argument(...),
    output: Path | None = typer.Option(None, "--output", "-o", dir_okay=False),
) -> None:
    """Export one archived evidence bundle as a ZIP file."""

    destination = export_run(run_id, output)
    console.print(f"Exported [bold]{destination}[/bold]")


@app.command("doctor")
def doctor_command(
    config: Path | None = typer.Option(None, "--config", exists=True, dir_okay=False),
) -> None:
    """Check control-plane prerequisites without running untrusted repository code."""

    run_async(run_doctor(config))


@app.command("harnesses")
def harnesses_command() -> None:
    """List supported harnesses and their verified integration modes."""

    table = Table(title="ReproForge harnesses")
    table.add_column("ID")
    table.add_column("Harness")
    table.add_column("Mode")
    table.add_column("Structured")
    table.add_column("Launchable")
    for capability in capability_catalog():
        table.add_row(
            capability.id,
            capability.display_name,
            ", ".join(mode.value for mode in capability.integration_modes),
            "yes" if capability.structured_output else "no",
            "yes" if capability.launchable else "no",
        )
    console.print(table)


@app.command("capabilities")
def capabilities_command(
    harness: str = typer.Argument(..., help="Harness id from `reproforge harnesses`."),
    detect: bool = typer.Option(
        False,
        "--detect",
        help="Also check whether the harness executable is installed on this host.",
    ),
) -> None:
    """Show the evidence-backed capability record for one harness."""

    if harness not in harness_ids():
        die(f"unknown harness {harness!r}; choose one of: {', '.join(harness_ids())}")
    capability = next(item for item in capability_catalog() if item.id == harness)
    payload = capability.model_dump(mode="json")
    if detect:
        detected = run_async_result(create_adapter(harness).detect())
        payload["host_detection"] = detected.model_dump(mode="json")
    console.print_json(json.dumps(payload))
