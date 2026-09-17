from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path

from reproforge.core.config import ReproForgeConfig
from reproforge.core.models import (
    CommandResult,
    CommandSpec,
    EnvironmentSnapshot,
    ReproductionReport,
    ReproductionRequest,
    RunStatus,
    utcnow,
)
from reproforge.repository.analyzer import RepositoryInspection
from reproforge.repository.git import GitRepository
from reproforge.sandbox.docker import DockerSession
from reproforge.security.redaction import redact

_BASE_FORBIDDEN_PATHS = frozenset(
    {
        "~/.ssh",
        "~/.aws",
        "~/.config/gh",
        "/var/run/docker.sock",
    }
)


async def run_commands(
    session: DockerSession,
    commands: list[CommandSpec],
) -> list[CommandResult]:
    results: list[CommandResult] = []
    for command in commands:
        result = await session.run(command)
        results.append(result)
        if not command_succeeded(result):
            break
    return results


def command_succeeded(result: CommandResult) -> bool:
    return not result.timed_out and result.exit_code == 0


def runtime_policy_error(config: ReproForgeConfig) -> str | None:
    if config.security.allowed_network_domains:
        return (
            "The Docker backend cannot enforce allowed_network_domains yet; "
            "refusing to execute with a domain allowlist configured."
        )
    return None


def workspace_policy_error(config: ReproForgeConfig, workspace: Path) -> str | None:
    resolved_workspace = workspace.expanduser().resolve()
    forbidden_paths = _BASE_FORBIDDEN_PATHS | frozenset(config.security.forbidden_filesystem_paths)
    for raw_path in forbidden_paths:
        forbidden = Path(raw_path).expanduser().resolve(strict=False)
        if _paths_intersect(resolved_workspace, forbidden):
            return (
                f"Workspace {resolved_workspace} intersects forbidden host path {forbidden}; "
                "refusing to inspect or mount it."
            )
    return None


def _paths_intersect(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


async def safe_revision(repository: GitRepository) -> str | None:
    try:
        return await repository.revision()
    except Exception:
        return None


async def safe_diff(repository: GitRepository) -> str | None:
    try:
        return await repository.diff()
    except Exception:
        return None


async def capture_repository_patch(
    repository: GitRepository,
    workspace: Path,
    filename: str,
    secret_values: tuple[str, ...],
) -> str | None:
    patch = await safe_diff(repository)
    if not patch:
        return None
    path = workspace / ".reproforge" / "patches" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(patch, secret_values=secret_values), encoding="utf-8")
    return str(path.relative_to(workspace))


def environment_snapshot(
    config: ReproForgeConfig,
    inspection: RepositoryInspection | None,
    revision: str | None,
) -> EnvironmentSnapshot:
    limits = config.sandbox.limits
    return EnvironmentSnapshot(
        backend="docker",
        image=config.sandbox.image,
        platform=platform.platform(),
        revision=revision,
        cpu_limit=limits.cpus,
        memory_limit_mb=limits.memory_mb,
        pids_limit=limits.pids,
        network_policy=config.sandbox.network,
        injected_environment_keys=sorted(config.selected_environment()),
        detected_project=inspection.profile if inspection is not None else None,
    )


def terminal_report(
    *,
    request: ReproductionRequest,
    run_id: str,
    started: datetime,
    environment: EnvironmentSnapshot,
    status: RunStatus,
    summary: str,
    setup_results: list[CommandResult] | None = None,
    baseline_results: list[CommandResult] | None = None,
    harness_results: list[CommandResult] | None = None,
    harness_id: str | None = None,
    harness_interpretation: str | None = None,
    generated_regression_test: str | None = None,
    caveats: list[str] | None = None,
    artifacts: dict[str, str] | None = None,
) -> ReproductionReport:
    return ReproductionReport(
        run_id=run_id,
        status=status,
        confidence=0.0 if status == RunStatus.INFRASTRUCTURE_FAILURE else 0.25,
        summary=summary,
        request=request,
        started_at=started,
        finished_at=utcnow(),
        environment=environment,
        setup_commands=setup_results or [],
        baseline_commands=baseline_results or [],
        harness_commands=harness_results or [],
        reproduction_rate=0.0,
        deterministic=False,
        baseline_ok=status not in {RunStatus.SETUP_FAILURE, RunStatus.INFRASTRUCTURE_FAILURE},
        harness_id=harness_id,
        harness_interpretation=harness_interpretation,
        generated_regression_test=generated_regression_test,
        caveats=caveats or [],
        artifacts=artifacts or {},
    )


def result_summary(status: RunStatus, rate: float, signal: str | None) -> str:
    base = f"Observed status {status.value} across {rate:.0%} of reproduction attempts."
    return f"{base} Primary signal: {signal}" if signal else base
