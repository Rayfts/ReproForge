from __future__ import annotations

import asyncio
import base64
import os
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    pass


@dataclass(slots=True)
class GitRepository:
    path: Path

    @classmethod
    async def clone(
        cls,
        url: str,
        destination: Path,
        *,
        revision: str | None = None,
        depth: int | None = None,
        auth_token: str | None = None,
    ) -> "GitRepository":
        destination.parent.mkdir(parents=True, exist_ok=True)
        argv = ["git", "clone", "--no-tags"]
        if depth is not None:
            argv += ["--depth", str(depth)]
        argv += [url, str(destination)]
        environment = _github_auth_environment(auth_token) if auth_token and _is_github_https(url) else None
        await _run(argv, cwd=destination.parent, environment=environment)
        repository = cls(destination)
        if revision:
            await repository.checkout(revision)
        return repository

    async def checkout(self, revision: str) -> None:
        await _run(["git", "checkout", "--detach", revision], cwd=self.path)

    async def revision(self) -> str:
        return (await _run(["git", "rev-parse", "HEAD"], cwd=self.path)).strip()

    async def status_porcelain(self) -> str:
        output = await _run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=self.path,
        )
        return "\n".join(line for line in output.splitlines() if not _is_reproforge_artifact(line[3:]))

    async def diff(self) -> str:
        tracked = await _run(["git", "diff", "--binary", "HEAD"], cwd=self.path)
        untracked_names = await _run(["git", "ls-files", "--others", "--exclude-standard"], cwd=self.path)
        chunks = [tracked]
        for name in [line for line in untracked_names.splitlines() if line]:
            if _is_reproforge_artifact(name):
                continue
            try:
                patch = await _run(
                    ["git", "diff", "--no-index", "--binary", "/dev/null", name],
                    cwd=self.path,
                    allowed=(0, 1),
                )
            except GitError:
                continue
            chunks.append(patch)
        return "\n".join(chunk for chunk in chunks if chunk)


def _is_reproforge_artifact(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return normalized == ".reproforge" or normalized.startswith(".reproforge/")


def _is_github_https(url: str) -> bool:
    return url.startswith("https://github.com/")


def _github_auth_environment(token: str) -> dict[str, str]:
    environment = dict(os.environ)
    try:
        index = int(environment.get("GIT_CONFIG_COUNT", "0"))
    except ValueError:
        index = 0
    credentials = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    environment["GIT_CONFIG_COUNT"] = str(index + 1)
    environment[f"GIT_CONFIG_KEY_{index}"] = "http.https://github.com/.extraheader"
    environment[f"GIT_CONFIG_VALUE_{index}"] = f"AUTHORIZATION: basic {credentials}"
    return environment


async def _run(
    argv: list[str],
    *,
    cwd: Path,
    allowed: tuple[int, ...] = (0,),
    environment: dict[str, str] | None = None,
) -> str:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode not in allowed:
        raise GitError(f"command failed ({proc.returncode}): {' '.join(argv)}\n{stderr.decode('utf-8', errors='replace')[:2000]}")
    return stdout.decode("utf-8", errors="replace")
