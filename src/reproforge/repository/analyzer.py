from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reproforge.core.models import ProjectProfile
from reproforge.detectors.project import detect_project

IMPORTANT_FILES = (
    "README.md",
    "README.rst",
    "README.txt",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "Dockerfile",
    "docker-compose.yml",
    "compose.yml",
    "Makefile",
    "Taskfile.yml",
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "Cargo.toml",
    "go.mod",
)


@dataclass(slots=True)
class RepositoryInspection:
    root: Path
    profile: ProjectProfile
    important_files: dict[str, str]
    workflow_files: list[str]


def inspect_repository(root: Path, *, max_file_bytes: int = 256_000) -> RepositoryInspection:
    important: dict[str, str] = {}
    for relative in IMPORTANT_FILES:
        path = root / relative
        if path.is_file() and path.stat().st_size <= max_file_bytes:
            important[relative] = path.read_text(encoding="utf-8", errors="replace")

    workflow_root = root / ".github" / "workflows"
    workflows: list[str] = []
    if workflow_root.is_dir():
        workflows = [
            str(path.relative_to(root))
            for path in sorted(workflow_root.iterdir())
            if path.suffix in {".yml", ".yaml"} and path.is_file()
        ]

    return RepositoryInspection(
        root=root,
        profile=detect_project(root),
        important_files=important,
        workflow_files=workflows,
    )
