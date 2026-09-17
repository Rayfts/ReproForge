from __future__ import annotations

from pathlib import Path

from reproforge.core.models import ReproductionRequest
from reproforge.github.client import GitHubClient


async def from_github_issue(url: str, *, harness: str | None = None) -> ReproductionRequest:
    issue = await GitHubClient().fetch_issue(url)
    return ReproductionRequest(
        source="github-issue",
        issue=issue,
        target_revision=issue.repository_default_branch,
        harness=harness,
    )


def from_local(path: Path, *, harness: str | None = None) -> ReproductionRequest:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"local repository does not exist or is not a directory: {resolved}")
    return ReproductionRequest(source="local", local_path=resolved, harness=harness)
