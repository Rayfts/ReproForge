from __future__ import annotations

import uuid
from collections.abc import Sequence
from pathlib import Path

from reproforge.core.config import ReproForgeConfig
from reproforge.core.models import (
    AttemptRecord,
    CommandResult,
    CommandSpec,
    ReproductionReport,
    ReproductionRequest,
    RunStatus,
    utcnow,
)
from reproforge.environments.planner import baseline_plan, setup_plan, test_plan
from reproforge.minimization.ddmin import ddmin
from reproforge.repository.analyzer import inspect_repository
from reproforge.repository.git import GitRepository
from reproforge.reports.writer import write_report_bundle
from reproforge.reproduction.investigation import HarnessPlan, investigate_harness
from reproforge.reproduction.support import (
    command_succeeded,
    environment_snapshot,
    result_summary,
    run_commands,
    runtime_policy_error,
    safe_revision,
    terminal_report,
)
from reproforge.sandbox.docker import DockerSandbox, DockerSession
from reproforge.security.redaction import redact
from reproforge.validation.oracles import classify_attempts, inspect_command


class ReproductionEngine:
    def __init__(self, config: ReproForgeConfig) -> None:
        self.config = config
        self.sandbox = DockerSandbox(config.sandbox)

    async def run(
        self,
        request: ReproductionRequest,
        *,
        workspace: Path,
    ) -> ReproductionReport:
        started = utcnow()
        run_id = uuid.uuid4().hex
        workspace = workspace.resolve()
        inspection = inspect_repository(workspace)
        repository = GitRepository(workspace)
        revision = await safe_revision(repository)
        environment = environment_snapshot(self.config, inspection, revision)
        selected_environment = self.config.selected_environment()
        secret_values = tuple(
            value
            for key, value in selected_environment.items()
            if key in self.config.security.allowed_secrets
        )

        policy_error = runtime_policy_error(self.config)
        if policy_error is not None:
            report = terminal_report(
                request=request,
                run_id=run_id,
                started=started,
                environment=environment,
                status=RunStatus.INFRASTRUCTURE_FAILURE,
                summary=policy_error,
                caveats=["No repository code was executed because the requested network policy cannot be enforced."],
            )
            write_report_bundle(workspace, report, secret_values=secret_values)
            return report

        if self.config.sandbox.image is None:
            report = terminal_report(
                request=request,
                run_id=run_id,
                started=started,
                environment=environment,
                status=RunStatus.INFRASTRUCTURE_FAILURE,
                summary=(
                    "No Docker image is configured. Set sandbox.image in .reproforge.yml "
                    "to an image containing the detected project runtimes."
                ),
                caveats=["ReproForge never falls back to executing untrusted project code on the host."],
            )
            write_report_bundle(workspace, report, secret_values=secret_values)
            return report

        setup_results: list[CommandResult] = []
        baseline_results: list[CommandResult] = []
        attempts: list[AttemptRecord] = []
        harness_interpretation: str | None = None
        generated_regression_test: str | None = None
        artifacts: dict[str, str] = {}
        caveats: list[str] = []

        session = await self.sandbox.open_session(
            workspace=workspace,
            image=self.config.sandbox.image,
            environment=selected_environment,
        )
        async with session:
            setup_results = await run_commands(session, setup_plan(inspection.profile, self.config))
            failed_setup = next((result for result in setup_results if not command_succeeded(result)), None)
            if failed_setup is not None:
                report = terminal_report(
                    request=request,
                    run_id=run_id,
                    started=started,
                    environment=environment,
                    status=RunStatus.SETUP_FAILURE,
                    summary=f"Repository setup failed: {' '.join(failed_setup.command.argv)}",
                    setup_results=setup_results,
                )
                write_report_bundle(workspace, report, secret_values=secret_values)
                return report

            baseline_results = await run_commands(session, baseline_plan(inspection.profile, self.config))
            failed_baseline = next(
                (result for result in baseline_results if not command_succeeded(result)),
                None,
            )
            if failed_baseline is not None:
                report = terminal_report(
                    request=request,
                    run_id=run_id,
                    started=started,
                    environment=environment,
                    status=RunStatus.SETUP_FAILURE,
                    summary=(
                        "Baseline build/check failed before reproduction investigation: "
                        + " ".join(failed_baseline.command.argv)
                    ),
                    setup_results=setup_results,
                    baseline_results=baseline_results,
                    caveats=[
                        "A pre-existing baseline failure prevents ReproForge from attributing later failures to the reported bug."
                    ],
                )
                write_report_bundle(workspace, report, secret_values=secret_values)
                return report

            selected_harness = request.harness or self.config.harness.preferred
            plan = HarnessPlan()
            if selected_harness:
                plan, harness_interpretation, harness_caveats = await investigate_harness(
                    self.sandbox,
                    self.config,
                    selected_harness,
                    request=request,
                    workspace=workspace,
                    inspection=inspection,
                )
                caveats.extend(harness_caveats)
                await self._capture_harness_patch(repository, workspace, secret_values, artifacts)
                generated_regression_test = plan.regression_test

            reproduction_commands = plan.reproduction_commands or test_plan(inspection.profile, self.config)
            if not reproduction_commands:
                report = terminal_report(
                    request=request,
                    run_id=run_id,
                    started=started,
                    environment=environment,
                    status=RunStatus.INSUFFICIENT_INFORMATION,
                    summary=(
                        "No deterministic reproduction command was provided by the harness or detected from the repository."
                    ),
                    setup_results=setup_results,
                    baseline_results=baseline_results,
                    harness_id=selected_harness,
                    harness_interpretation=harness_interpretation,
                    generated_regression_test=generated_regression_test,
                    caveats=caveats,
                    artifacts=artifacts,
                )
                write_report_bundle(workspace, report, secret_values=secret_values)
                return report

            for number in range(1, self.config.reproduction_attempts + 1):
                attempts.append(await self._attempt(session, number=number, commands=reproduction_commands))

            status, rate, deterministic, confidence, primary = classify_attempts(
                attempts,
                flake_threshold=self.config.flake_threshold,
            )
            minimized = await self._maybe_minimize(session, reproduction_commands, primary.fingerprint if primary else None)

            report = ReproductionReport(
                run_id=run_id,
                status=status,
                confidence=confidence,
                summary=result_summary(status, rate, primary.summary if primary else None),
                request=request,
                started_at=started,
                finished_at=utcnow(),
                environment=environment,
                setup_commands=setup_results,
                baseline_commands=baseline_results,
                attempts=attempts,
                primary_signal=primary,
                reproduction_rate=rate,
                deterministic=deterministic,
                baseline_ok=True,
                harness_id=selected_harness,
                harness_interpretation=harness_interpretation,
                generated_regression_test=generated_regression_test,
                minimized_reproduction=minimized,
                caveats=caveats,
                artifacts=artifacts,
            )
            write_report_bundle(workspace, report, secret_values=secret_values)
            return report

    async def _attempt(
        self,
        session: DockerSession,
        *,
        number: int,
        commands: list[CommandSpec],
    ) -> AttemptRecord:
        results = await run_commands(session, commands)
        signals = [
            signal
            for index, result in enumerate(results)
            for signal in inspect_command(result, command_index=index)
        ]
        return AttemptRecord(attempt=number, commands=results, signals=signals, reproduced=bool(signals))

    async def _maybe_minimize(
        self,
        session: DockerSession,
        commands: list[CommandSpec],
        fingerprint: str | None,
    ) -> str | None:
        if not fingerprint or not self.config.minimization.enabled or len(commands) <= 1:
            return None
        minimized = await self._minimize_commands(session, commands=commands, fingerprint=fingerprint)
        if len(minimized) >= len(commands):
            return None
        return "\n".join(" ".join(command.argv) for command in minimized)

    async def _minimize_commands(
        self,
        session: DockerSession,
        *,
        commands: list[CommandSpec],
        fingerprint: str,
    ) -> list[CommandSpec]:
        async def preserves(candidate: Sequence[CommandSpec]) -> bool:
            results = await run_commands(session, list(candidate))
            signals = [
                signal
                for index, result in enumerate(results)
                for signal in inspect_command(result, command_index=index)
            ]
            return any(signal.fingerprint == fingerprint for signal in signals)

        return await ddmin(commands, preserves, max_trials=self.config.minimization.max_trials)

    async def _capture_harness_patch(
        self,
        repository: GitRepository,
        workspace: Path,
        secret_values: tuple[str, ...],
        artifacts: dict[str, str],
    ) -> None:
        patch = await repository.diff()
        if not patch:
            return
        patch_path = workspace / ".reproforge" / "patches" / "harness.patch"
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(redact(patch, secret_values=secret_values), encoding="utf-8")
        artifacts["harness_patch"] = str(patch_path.relative_to(workspace))
