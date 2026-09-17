from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, field_validator

from reproforge.core.models import CommandSpec, StrictModel

_CONTROL_PLANE_SECRETS = frozenset({"GITHUB_TOKEN", "GH_TOKEN"})


class ResourceLimits(StrictModel):
    timeout_seconds: int = Field(default=600, ge=1, le=86_400)
    memory_mb: int = Field(default=2048, ge=128, le=131_072)
    cpus: float = Field(default=2.0, gt=0, le=64)
    pids: int = Field(default=256, ge=16, le=32_768)


class SandboxConfig(StrictModel):
    backend: Literal["docker"] = "docker"
    image: str | None = None
    network: Literal["none", "bridge"] = "none"
    read_only_root: bool = True
    limits: ResourceLimits = Field(default_factory=ResourceLimits)


class HarnessConfig(StrictModel):
    preferred: str | None = None
    image: str | None = None
    allow_host_execution: bool = False
    extra_args: list[str] = Field(default_factory=list)


class SecurityConfig(StrictModel):
    allowed_secrets: list[str] = Field(default_factory=list)
    allowed_environment: list[str] = Field(default_factory=list)
    allowed_network_domains: list[str] = Field(default_factory=list)
    forbidden_filesystem_paths: list[str] = Field(
        default_factory=lambda: ["~/.ssh", "~/.aws", "~/.config/gh", "/var/run/docker.sock"]
    )

    @field_validator("allowed_secrets", "allowed_environment")
    @classmethod
    def validate_env_keys(cls, value: list[str]) -> list[str]:
        for key in value:
            if not key or "=" in key or "\x00" in key:
                raise ValueError(f"invalid environment key: {key!r}")
        return value


class MinimizationConfig(StrictModel):
    enabled: bool = True
    max_trials: int = Field(default=32, ge=1, le=1000)


class ReproForgeConfig(StrictModel):
    setup: list[CommandSpec] = Field(default_factory=list)
    build: CommandSpec | None = None
    tests: list[CommandSpec] = Field(default_factory=list)
    runtime_versions: dict[str, str] = Field(default_factory=dict)
    required_services: list[str] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    reproduction_attempts: int = Field(default=3, ge=1, le=20)
    flake_threshold: float = Field(default=0.34, ge=0, le=1)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    harness: HarnessConfig = Field(default_factory=HarnessConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    minimization: MinimizationConfig = Field(default_factory=MinimizationConfig)

    def selected_environment(self) -> dict[str, str]:
        selected: dict[str, str] = dict(self.environment)
        environment_grants = _operator_grants("REPROFORGE_ENV_GRANTS")
        secret_grants = _operator_grants("REPROFORGE_SECRET_GRANTS")

        for key in self.security.allowed_environment:
            if key in environment_grants and key in os.environ:
                selected[key] = os.environ[key]
        for key in self.security.allowed_secrets:
            if key in _CONTROL_PLANE_SECRETS:
                continue
            if key in secret_grants and key in os.environ:
                selected[key] = os.environ[key]
        return selected


def load_config(path: Path | None, *, cwd: Path | None = None) -> ReproForgeConfig:
    root = cwd or Path.cwd()
    candidate = path or root / ".reproforge.yml"
    if not candidate.exists():
        return ReproForgeConfig()
    raw = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{candidate} must contain a YAML mapping")
    return ReproForgeConfig.model_validate(raw)


def dump_default_config() -> str:
    data: dict[str, Any] = ReproForgeConfig().model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(data, sort_keys=False)


def _operator_grants(name: str) -> set[str]:
    raw = os.getenv(name, "")
    return {item.strip() for item in raw.split(",") if item.strip()}
