from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from rich.table import Table

from reproforge.cli.runtime import (
    archive_run,
    console,
    die,
    home,
    load_archived_run,
    print_report,
    store,
    validate_harness,
)
from reproforge.core.config import ReproForgeConfig, load_config
from reproforge.core.models import ReproductionReport, ReproductionRequest
from reproforge.github.client import GitHubClient, GitHubError
from reproforge.repository.git import GitRepository
from reproforge.reports.github import render_issue_comment
from reproforge.reproduction.engine import ReproductionEngine
from reproforge.sandbox.docker import DockerSandbox


async def run_issue(
    *,
    url: str,
    harness: str | None,
    revision: str | None,
    image: str | None,
    harness_image: str | None,
    config_path: Path | None,
    post_comment: bool = False,
) -> None:
    validate_harness(harness)
    client = GitHubClient()
    issue = await client.fetch_issue(url)
    workspace = home() / "workspaces" / uuid.uuid4().hex
    console.print(f"Cloning [bold]{issue.ref.owner}/{issue.ref.repo}[/bold] into {workspace}")
    await GitRepository.clone(
        issue.repository_clone_url,
        workspace,
        revision=revision,
        auth_token=client.resolved_token(),
    )
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
    report = await _execute_and_archive(cfg, request, workspace)
    if post_comment:
        try:
            await client.post_issue_comment(issue.ref, render_issue_comment(report))
        except GitHubError as exc:
            console.print(f"[yellow]Evidence saved, but issue comment could not be posted: {exc}[/yellow]")


async def run_local(
    *,
    path: Path,
    harness: str | None,
    image: str | None,
    harness_image: str | None,
    config_path: Path | None,
) -> None:
    validate_harness(harness)
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
    await _execute_and_archive(cfg, request, workspace)


async def resume_run(*, run_id: str, harness: str | None, image: str | None) -> None:
    validate_harness(harness)
    previous, archive = load_archived_run(run_id)
    metadata_path = archive / "metadata.json"
    if not metadata_path.is_file():
        die(f"run {run_id} does not contain workspace metadata")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    workspace = Path(str(metadata["workspace"])).expanduser().resolve()
    if not workspace.is_dir():
        die(f"stored workspace no longer exists: {workspace}")
    selected_harness = harness or previous.request.harness
    cfg = _configured(
        load_config(None, cwd=workspace),
        harness=selected_harness,
        image=image,
        harness_image=None,
    )
    request = previous.request.model_copy(update={"harness": selected_harness})
    await _execute_and_archive(cfg, request, workspace)


async def run_doctor(config_path: Path | None) -> None:
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


async def _execute_and_archive(
    config: ReproForgeConfig,
    request: ReproductionRequest,
    workspace: Path,
) -> ReproductionReport:
    report = await ReproductionEngine(config).run(request, workspace=workspace)
    archive = archive_run(workspace, report)
    store().upsert(report.run_id, archive, report.status.value)
    print_report(report)
    return report


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
