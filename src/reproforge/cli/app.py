from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
import zipfile
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, Never, TypeVar

import typer
from rich.console import Console
from rich.table import Table

from reproforge import __version__
from reproforge.core.config import ReproForgeConfig, load_config
from reproforge.core.models import ReproductionReport, ReproductionRequest
from reproforge.github.client import GitHubClient
from reproforge.harnesses import capability_catalog, create_adapter, harness_ids
from reproforge.repository.git import GitRepository
from reproforge.reproduction.engine import ReproductionEngine
from reproforge.sandbox.docker import DockerSandbox
from reproforge.store.runs import RunStore

app = typer.Typer(
    name="reproforge",
    no_args_is_help=True,
    help="Turn bug reports into reproducible evidence.",
)
console = Console()
error_console = Console(stderr=True)
T = TypeVar("T")

_EVIDENCE_FILES = (
    "report.json",
    "report.md",
    "environment.json",
    "attempts.jsonl",
    "commands.jsonl",
)
_EVIDENCE_DIRS = ("logs", "patches", "artifacts", "reproduction", "regression-test")


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

    _run_async(
        _issue(
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

    _run_async(
        _local(
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

    _run_async(_resume(run_id=run_id, harness=harness, image=image))


@app.command("inspect")
def inspect_command(
    run_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json", help="Print the full report JSON."),
) -> None:
    """Inspect an archived run without executing code."""

    report, _ = _load_archived_run(run_id)
    if as_json:
        console.print_json(report.model_dump_json(indent=2))
        return
    _print_report(report)


@app.command("export")
def export_command(
    run_id: str = typer.Argument(...),
    output: Path | None = typer.Option(None, "--output", "-o", dir_okay=False),
) -> None:
    """Export one archived evidence bundle as a ZIP file."""

    _, archive = _load_archived_run(run_id)
    destination = (output or Path.cwd() / f"reproforge-{run_id}.zip").resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(archive.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(archive))
    console.print(f"Exported [bold]{destination}[/bold]")


@app.command("doctor")
def doctor_command(
    config: Path | None = typer.Option(None, "--config", exists=True, dir_okay=False),
) -> None:
    """Check control-plane prerequisites without running untrusted repository code."""

    _run_async(_doctor(config))


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
        _die(f"unknown harness {harness!r}; choose one of: {', '.join(harness_ids())}")
    capability = next(item for item in capability_catalog() if item.id == harness)
    payload = capability.model_dump(mode="json")
    if detect:
        detected = _run_async_result(create_adapter(harness).detect())
        payload["host_detection"] = detected.model_dump(mode="json")
    console.print_json(json.dumps(payload))


async def _issue(
    *,
    url: str,
    harness: str | None,
    revision: str | None,
    image: str | None,
    harness_image: str | None,
    config_path: Path | None,
) -> None:
    _validate_harness(harness)
    issue = await GitHubClient().fetch_issue(url)
    workspace = _home() / "workspaces" / uuid.uuid4().hex
    console.print(f"Cloning [bold]{issue.ref.owner}/{issue.ref.repo}[/bold] into {workspace}")
    await GitRepository.clone(issue.repository_clone_url, workspace, revision=revision)
    cfg = _configured(
        load_config(config_path, cwd=workspace),
        harness=harness,
        image=image,
        harness_image=harness_image,
    )
    request = ReproductionRequest(
        source="github-issue",
        issue=issue,
        target_revision=revision,
        harness=harness or cfg.harness.preferred,
    )
    report = await ReproductionEngine(cfg).run(request, workspace=workspace)
    archive = _archive_run(workspace, report)
    _store().upsert(report.run_id, archive, report.status.value)
    _print_report(report)


async def _local(
    *,
    path: Path,
    harness: str | None,
    image: str | None,
    harness_image: str | None,
    config_path: Path | None,
) -> None:
    _validate_harness(harness)
    workspace = path.resolve()
    cfg = _configured(
        load_config(config_path, cwd=workspace),
        harness=harness,
        image=image,
        harness_image=harness_image,
    )
    request = ReproductionRequest(
        source="local",
        local_path=workspace,
        harness=harness or cfg.harness.preferred,
    )
    report = await ReproductionEngine(cfg).run(request, workspace=workspace)
    archive = _archive_run(workspace, report)
    _store().upsert(report.run_id, archive, report.status.value)
    _print_report(report)


async def _resume(*, run_id: str, harness: str | None, image: str | None) -> None:
    _validate_harness(harness)
    previous, archive = _load_archived_run(run_id)
    metadata_path = archive / "metadata.json"
    if not metadata_path.is_file():
        _die(f"run {run_id} does not contain workspace metadata")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    workspace = Path(str(metadata["workspace"])).expanduser().resolve()
    if not workspace.is_dir():
        _die(f"stored workspace no longer exists: {workspace}")
    cfg = _configured(
        load_config(None, cwd=workspace),
        harness=harness or previous.request.harness,
        image=image,
        harness_image=None,
    )
    request = previous.request.model_copy(update={"harness": harness or previous.request.harness})
    report = await ReproductionEngine(cfg).run(request, workspace=workspace)
    next_archive = _archive_run(workspace, report)
    _store().upsert(report.run_id, next_archive, report.status.value)
    _print_report(report)


async def _doctor(config_path: Path | None) -> None:
    cfg = load_config(config_path, cwd=Path.cwd())
    table = Table(title="ReproForge doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    git = shutil.which("git")
    table.add_row("Git", "OK" if git else "MISSING", git or "git is required")

    docker = DockerSandbox(cfg.sandbox)
    docker_ok = await docker.available()
    table.add_row(
        "Docker",
        "OK" if docker_ok else "MISSING",
        "daemon reachable" if docker_ok else "Docker is required for untrusted execution",
    )
    table.add_row(
        "Sandbox image",
        "OK" if cfg.sandbox.image else "UNSET",
        cfg.sandbox.image or "set sandbox.image in .reproforge.yml or pass --image",
    )
    table.add_row(
        "Network",
        "LOCKED" if cfg.sandbox.network == "none" else "ENABLED",
        cfg.sandbox.network,
    )
    table.add_row(
        "Allowed secrets",
        str(len(cfg.security.allowed_secrets)),
        ", ".join(cfg.security.allowed_secrets) or "none (recommended default)",
    )
    console.print(table)


def _configured(
    config: ReproForgeConfig,
    *,
    harness: str | None,
    image: str | None,
    harness_image: str | None,
) -> ReproForgeConfig:
    if harness:
        config.harness.preferred = harness
    if image:
        config.sandbox.image = image
    if harness_image:
        config.harness.image = harness_image
    return config


def _archive_run(workspace: Path, report: ReproductionReport) -> Path:
    source = workspace / ".reproforge"
    archive = _home() / "runs" / report.run_id
    if archive.exists():
        shutil.rmtree(archive)
    archive.mkdir(parents=True)
    for name in _EVIDENCE_FILES:
        path = source / name
        if path.is_file():
            shutil.copy2(path, archive / name)
    for name in _EVIDENCE_DIRS:
        path = source / name
        if path.is_dir():
            shutil.copytree(path, archive / name)
    (archive / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": report.run_id,
                "workspace": str(workspace.resolve()),
                "source": report.request.source,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return archive


def _load_archived_run(run_id: str) -> tuple[ReproductionReport, Path]:
    stored = _store().get(run_id)
    if stored is None:
        _die(f"unknown run id: {run_id}")
    report_path = stored.path / "report.json"
    if not report_path.is_file():
        _die(f"archived report is missing: {report_path}")
    return ReproductionReport.model_validate_json(report_path.read_text(encoding="utf-8")), stored.path


def _print_report(report: ReproductionReport) -> None:
    table = Table(title=f"ReproForge {report.run_id}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Status", report.status.value)
    table.add_row("Confidence", f"{report.confidence:.2f}")
    table.add_row("Reproduction rate", f"{report.reproduction_rate:.0%}")
    table.add_row("Deterministic", "yes" if report.deterministic else "no")
    table.add_row("Baseline healthy", "yes" if report.baseline_ok else "no")
    table.add_row("Harness", report.harness_id or "none")
    console.print(table)
    console.print(report.summary)


def _validate_harness(harness: str | None) -> None:
    if harness is not None and harness not in harness_ids():
        _die(f"unknown harness {harness!r}; choose one of: {', '.join(harness_ids())}")


def _home() -> Path:
    root = Path(os.environ.get("REPROFORGE_HOME", "~/.reproforge")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _store() -> RunStore:
    return RunStore(_home() / "state")


def _run_async(coro: Coroutine[Any, Any, None]) -> None:
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    except Exception as exc:
        error_console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


def _run_async_result(coro: Coroutine[Any, Any, T]) -> T:
    try:
        return asyncio.run(coro)
    except Exception as exc:
        error_console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


def _die(message: str) -> Never:
    error_console.print(f"[bold red]error:[/bold red] {message}")
    raise typer.Exit(code=2)
