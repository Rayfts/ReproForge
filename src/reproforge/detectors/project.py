from __future__ import annotations

import json
import tomllib
from pathlib import Path

from reproforge.core.models import CommandSpec, ProjectProfile


def detect_project(root: Path) -> ProjectProfile:
    profile = ProjectProfile()
    _detect_python(root, profile)
    _detect_node(root, profile)
    _detect_rust(root, profile)
    _detect_go(root, profile)
    _detect_services(root, profile)
    profile.languages = sorted(set(profile.languages))
    profile.frameworks = sorted(set(profile.frameworks))
    profile.package_managers = sorted(set(profile.package_managers))
    profile.test_runners = sorted(set(profile.test_runners))
    profile.manifests = sorted(set(profile.manifests))
    profile.lockfiles = sorted(set(profile.lockfiles))
    profile.services = sorted(set(profile.services))
    profile.setup_commands = _dedupe_commands(profile.setup_commands)
    profile.baseline_commands = _dedupe_commands(profile.baseline_commands)
    profile.test_commands = _dedupe_commands(profile.test_commands)
    return profile


def _detect_python(root: Path, profile: ProjectProfile) -> None:
    pyproject = root / "pyproject.toml"
    requirements = root / "requirements.txt"
    uv_lock = root / "uv.lock"
    poetry_lock = root / "poetry.lock"
    has_python = pyproject.exists() or requirements.exists() or any(root.rglob("*.py"))
    if not has_python:
        return
    profile.languages.append("Python")
    data: dict[str, object] = {}
    if pyproject.exists():
        profile.manifests.append("pyproject.toml")
        try:
            parsed = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                data = parsed
        except (tomllib.TOMLDecodeError, OSError):
            pass
    project = data.get("project", {}) if isinstance(data, dict) else {}
    dependencies = project.get("dependencies", []) if isinstance(project, dict) else []
    joined = " ".join(str(item).lower() for item in dependencies)
    if "fastapi" in joined:
        profile.frameworks.append("FastAPI")
        profile.services.append("HTTP API")
    if "django" in joined:
        profile.frameworks.append("Django")
        profile.services.append("HTTP server")
    if "flask" in joined:
        profile.frameworks.append("Flask")
        profile.services.append("HTTP server")
    if "pytest" in joined or (root / "pytest.ini").exists() or (root / "tests").is_dir():
        profile.test_runners.append("pytest")
        profile.test_commands.append(
            CommandSpec(argv=["python", "-m", "pytest", "-q"], purpose="test")
        )
    if uv_lock.exists():
        profile.lockfiles.append("uv.lock")
        profile.package_managers.append("uv")
        profile.setup_commands.append(CommandSpec(argv=["uv", "sync", "--frozen"], purpose="setup"))
    elif poetry_lock.exists():
        profile.lockfiles.append("poetry.lock")
        profile.package_managers.append("poetry")
        profile.setup_commands.append(
            CommandSpec(argv=["poetry", "install", "--no-interaction"], purpose="setup")
        )
    elif requirements.exists():
        profile.manifests.append("requirements.txt")
        profile.package_managers.append("pip")
        profile.setup_commands.append(
            CommandSpec(
                argv=["python", "-m", "pip", "install", "-r", "requirements.txt"],
                purpose="setup",
            )
        )
    elif pyproject.exists():
        profile.package_managers.append("pip")
        profile.setup_commands.append(
            CommandSpec(argv=["python", "-m", "pip", "install", "-e", "."], purpose="setup")
        )


def _detect_node(root: Path, profile: ProjectProfile) -> None:
    package = root / "package.json"
    if not package.exists():
        if any(root.rglob("*.ts")) or any(root.rglob("*.tsx")):
            profile.languages.append("TypeScript")
        elif any(root.rglob("*.js")) or any(root.rglob("*.jsx")):
            profile.languages.append("JavaScript")
        return
    profile.manifests.append("package.json")
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    combined = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    keys = {str(key).lower() for key in combined}
    if "typescript" in keys or any(root.rglob("*.ts")) or any(root.rglob("*.tsx")):
        profile.languages.append("TypeScript")
    else:
        profile.languages.append("JavaScript")
    if "react" in keys:
        profile.frameworks.append("React")
    if "next" in keys:
        profile.frameworks.append("Next.js")
        profile.services.append("HTTP server")
    if "express" in keys or "fastify" in keys or "koa" in keys:
        profile.services.append("HTTP API")
    scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
    lock_candidates = [
        ("pnpm-lock.yaml", "pnpm", ["pnpm", "install", "--frozen-lockfile"]),
        ("yarn.lock", "yarn", ["yarn", "install", "--frozen-lockfile"]),
        ("bun.lock", "bun", ["bun", "install", "--frozen-lockfile"]),
        ("bun.lockb", "bun", ["bun", "install", "--frozen-lockfile"]),
        ("package-lock.json", "npm", ["npm", "ci"]),
    ]
    manager = "npm"
    setup = ["npm", "install"]
    for lock, candidate_manager, command in lock_candidates:
        if (root / lock).exists():
            profile.lockfiles.append(lock)
            manager, setup = candidate_manager, command
            break
    profile.package_managers.append(manager)
    profile.setup_commands.append(CommandSpec(argv=setup, purpose="setup"))
    if isinstance(scripts, dict) and "test" in scripts:
        profile.test_runners.append(_node_test_runner(keys))
        profile.test_commands.append(CommandSpec(argv=[manager, "test"], purpose="test"))
    if isinstance(scripts, dict) and "build" in scripts:
        profile.baseline_commands.append(
            CommandSpec(argv=[manager, "run", "build"], purpose="build")
        )


def _node_test_runner(keys: set[str]) -> str:
    for name in ("vitest", "jest", "mocha", "ava"):
        if name in keys:
            return name
    return "package-script"


def _detect_rust(root: Path, profile: ProjectProfile) -> None:
    if not (root / "Cargo.toml").exists():
        return
    profile.languages.append("Rust")
    profile.package_managers.append("cargo")
    profile.test_runners.append("cargo test")
    profile.manifests.append("Cargo.toml")
    if (root / "Cargo.lock").exists():
        profile.lockfiles.append("Cargo.lock")
    profile.baseline_commands.append(
        CommandSpec(argv=["cargo", "check", "--all-targets"], purpose="build")
    )
    profile.test_commands.append(
        CommandSpec(argv=["cargo", "test", "--all-targets"], purpose="test")
    )


def _detect_go(root: Path, profile: ProjectProfile) -> None:
    if not (root / "go.mod").exists():
        return
    profile.languages.append("Go")
    profile.package_managers.append("go modules")
    profile.test_runners.append("go test")
    profile.manifests.append("go.mod")
    if (root / "go.sum").exists():
        profile.lockfiles.append("go.sum")
    profile.setup_commands.append(CommandSpec(argv=["go", "mod", "download"], purpose="setup"))
    profile.test_commands.append(CommandSpec(argv=["go", "test", "./..."], purpose="test"))


def _detect_services(root: Path, profile: ProjectProfile) -> None:
    for candidate in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        if (root / candidate).exists():
            profile.manifests.append(candidate)
            profile.services.append("Docker Compose services")
            break


def _dedupe_commands(commands: list[CommandSpec]) -> list[CommandSpec]:
    seen: set[tuple[str, ...]] = set()
    output: list[CommandSpec] = []
    for command in commands:
        key = tuple(command.argv)
        if key in seen:
            continue
        seen.add(key)
        output.append(command)
    return output
