from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

REPORT_SCHEMA_VERSION = "1.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


class RunStatus(StrEnum):
    REPRODUCED = "reproduced"
    PROBABLY_REPRODUCED = "probably-reproduced"
    NOT_REPRODUCED = "not-reproduced"
    FLAKY = "flaky"
    INSUFFICIENT_INFORMATION = "insufficient-information"
    SETUP_FAILURE = "setup-failure"
    INFRASTRUCTURE_FAILURE = "infrastructure-failure"
    INVALID_REPORT = "invalid-report"
    INCONCLUSIVE = "inconclusive"


class FailureKind(StrEnum):
    TEST_FAILURE = "failing-test"
    ASSERTION_MISMATCH = "assertion-mismatch"
    NONZERO_EXIT = "non-zero-exit"
    EXCEPTION = "exception"
    PANIC = "panic"
    CRASH = "crash"
    OUTPUT_MISMATCH = "output-mismatch"
    HTTP_MISMATCH = "http-response-mismatch"
    SNAPSHOT_MISMATCH = "snapshot-mismatch"
    COMPILER_ERROR = "compiler-error"
    RUNTIME_ERROR = "runtime-error"
    TIMEOUT = "timeout"
    RESOURCE_FAILURE = "resource-failure"


class EvidenceSource(StrEnum):
    OBSERVED = "observed"
    HARNESS = "harness"
    USER = "user"
    INFERRED = "inferred"


class CommandSpec(StrictModel):
    argv: list[str]
    cwd: str = "/workspace"
    env: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=300, ge=1, le=86_400)
    purpose: str = "unspecified"

    @field_validator("argv")
    @classmethod
    def argv_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("argv must contain at least one element")
        return value


class CommandResult(StrictModel):
    command: CommandSpec
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    started_at: datetime
    finished_at: datetime
    timed_out: bool = False
    duration_seconds: float = Field(ge=0)


class FailureSignal(StrictModel):
    kind: FailureKind
    summary: str
    source: EvidenceSource = EvidenceSource.OBSERVED
    command_index: int | None = None
    fingerprint: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AttemptRecord(StrictModel):
    attempt: int = Field(ge=1)
    commands: list[CommandResult] = Field(default_factory=list)
    signals: list[FailureSignal] = Field(default_factory=list)
    reproduced: bool = False
    filesystem_diff_path: str | None = None
    log_paths: list[str] = Field(default_factory=list)


class ProjectProfile(StrictModel):
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    test_runners: list[str] = Field(default_factory=list)
    manifests: list[str] = Field(default_factory=list)
    lockfiles: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    setup_commands: list[CommandSpec] = Field(default_factory=list)
    baseline_commands: list[CommandSpec] = Field(default_factory=list)
    test_commands: list[CommandSpec] = Field(default_factory=list)


class EnvironmentSnapshot(StrictModel):
    backend: str
    image: str | None = None
    platform: str
    revision: str | None = None
    cpu_limit: float | None = None
    memory_limit_mb: int | None = None
    pids_limit: int | None = None
    network_policy: str
    injected_environment_keys: list[str] = Field(default_factory=list)
    detected_project: ProjectProfile | None = None


class IssueRef(StrictModel):
    owner: str
    repo: str
    number: int = Field(ge=1)
    url: HttpUrl


class IssueMetadata(StrictModel):
    ref: IssueRef
    title: str
    body: str = ""
    state: str
    labels: list[str] = Field(default_factory=list)
    repository_clone_url: str
    repository_default_branch: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReproductionRequest(StrictModel):
    source: Literal["github-issue", "local"]
    issue: IssueMetadata | None = None
    local_path: Path | None = None
    target_revision: str | None = None
    harness: str | None = None


class ReproductionReport(StrictModel):
    schema_version: Literal["1.0"] = REPORT_SCHEMA_VERSION
    run_id: str
    status: RunStatus
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    request: ReproductionRequest
    started_at: datetime
    finished_at: datetime
    environment: EnvironmentSnapshot
    setup_commands: list[CommandResult] = Field(default_factory=list)
    baseline_commands: list[CommandResult] = Field(default_factory=list)
    harness_commands: list[CommandResult] = Field(default_factory=list)
    attempts: list[AttemptRecord] = Field(default_factory=list)
    primary_signal: FailureSignal | None = None
    reproduction_rate: float = Field(ge=0.0, le=1.0)
    deterministic: bool = False
    baseline_ok: bool = False
    harness_id: str | None = None
    harness_interpretation: str | None = None
    generated_regression_test: str | None = None
    minimized_reproduction: str | None = None
    caveats: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)


def utcnow() -> datetime:
    return datetime.now(UTC)
