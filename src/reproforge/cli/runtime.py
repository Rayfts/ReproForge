from __future__ import annotations

import asyncio
import json
import os
import shutil
import zipfile
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, Never, TypeVar

import typer
from rich.console import Console
from rich.table import Table

from reproforge.core.models import ReproductionReport
from reproforge.harnesses import harness_ids
from reproforge.reports.writer import write_report_bundle
from reproforge.store.runs import RunStore

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


def home() -> Path:
    root = Path(os.environ.get("REPROFORGE_HOME", "~/.reproforge")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


def store() -> RunStore:
    return RunStore(home() / "state")


def archive_run(
    workspace: Path,
    report: ReproductionReport,
    *,
    secret_values: tuple[str, ...] = (),
) -> Path:
    source = workspace / ".reproforge"
    archive = home() / "runs" / report.run_id
    if archive.exists():
        shutil.rmtree(archive)
    archive.mkdir(parents=True)
    _copy_evidence(source, archive)

    if not (archive / "report.json").is_file():
        staging_root = home() / "staging" / report.run_id
        if staging_root.exists():
            shutil.rmtree(staging_root)
        staging_bundle = write_report_bundle(staging_root, report, secret_values=secret_values)
        _copy_evidence(staging_bundle, archive)
        shutil.rmtree(staging_root, ignore_errors=True)

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


def _copy_evidence(source: Path, archive: Path) -> None:
    for name in _EVIDENCE_FILES:
        path = source / name
        if path.is_file():
            shutil.copy2(path, archive / name)
    for name in _EVIDENCE_DIRS:
        path = source / name
        destination = archive / name
        if path.is_dir() and not destination.exists():
            shutil.copytree(path, destination)


def load_archived_run(run_id: str) -> tuple[ReproductionReport, Path]:
    stored = store().get(run_id)
    if stored is None:
        die(f"unknown run id: {run_id}")
    report_path = stored.path / "report.json"
    if not report_path.is_file():
        die(f"archived report is missing: {report_path}")
    return ReproductionReport.model_validate_json(report_path.read_text(encoding="utf-8")), stored.path


def export_run(run_id: str, output: Path | None) -> Path:
    _, archive = load_archived_run(run_id)
    destination = (output or Path.cwd() / f"reproforge-{run_id}.zip").resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(archive.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(archive))
    return destination


def print_report(report: ReproductionReport) -> None:
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


def validate_harness(harness: str | None) -> None:
    if harness is not None and harness not in harness_ids():
        die(f"unknown harness {harness!r}; choose one of: {', '.join(harness_ids())}")


def run_async(coro: Coroutine[Any, Any, None]) -> None:
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    except Exception as exc:
        error_console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


def run_async_result(coro: Coroutine[Any, Any, T]) -> T:
    try:
        return asyncio.run(coro)
    except Exception as exc:
        error_console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


def die(message: str) -> Never:
    error_console.print(f"[bold red]error:[/bold red] {message}")
    raise typer.Exit(code=2)
