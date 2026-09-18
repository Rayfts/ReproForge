from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from datetime import datetime

import httpx

from reproforge.core.models import IssueMetadata, IssueRef

_ISSUE_RE = re.compile(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)(?:[/?#].*)?$")


class GitHubError(RuntimeError):
    pass


@dataclass(slots=True)
class GitHubClient:
    token: str | None = None
    base_url: str = "https://api.github.com"
    timeout: float = 20.0

    def resolved_token(self) -> str | None:
        return self.token or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ReproForge/0.1",
        }
        token = self.resolved_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def parse_issue_url(url: str) -> IssueRef:
        match = _ISSUE_RE.match(url.strip())
        if not match:
            raise ValueError("expected a GitHub issue URL like https://github.com/org/repo/issues/123")
        return IssueRef.model_validate(
            {
                "owner": match.group("owner"),
                "repo": match.group("repo"),
                "number": int(match.group("number")),
                "url": url,
            }
        )

    async def fetch_issue(self, url: str) -> IssueMetadata:
        ref = self.parse_issue_url(url)
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            issue_response, repo_response = await asyncio.gather(
                client.get(f"/repos/{ref.owner}/{ref.repo}/issues/{ref.number}"),
                client.get(f"/repos/{ref.owner}/{ref.repo}"),
            )
        if issue_response.status_code != 200:
            raise GitHubError(
                f"GitHub issue lookup failed with HTTP {issue_response.status_code}: "
                f"{_safe_message(issue_response)}"
            )
        if repo_response.status_code != 200:
            raise GitHubError(
                f"GitHub repository lookup failed with HTTP {repo_response.status_code}: "
                f"{_safe_message(repo_response)}"
            )
        issue = issue_response.json()
        repo = repo_response.json()
        if "pull_request" in issue:
            raise GitHubError("the URL points to a pull request, not an issue")
        return IssueMetadata(
            ref=ref,
            title=str(issue.get("title") or ""),
            body=str(issue.get("body") or ""),
            state=str(issue.get("state") or "unknown"),
            labels=[str(label.get("name")) for label in issue.get("labels", []) if label.get("name")],
            repository_clone_url=str(repo["clone_url"]),
            repository_default_branch=str(repo["default_branch"]),
            created_at=_parse_datetime(issue.get("created_at")),
            updated_at=_parse_datetime(issue.get("updated_at")),
        )

    async def post_issue_comment(self, issue: IssueRef, body: str) -> None:
        if not self.resolved_token():
            raise GitHubError("posting a comment requires GITHUB_TOKEN or GH_TOKEN")
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                f"/repos/{issue.owner}/{issue.repo}/issues/{issue.number}/comments",
                json={"body": body},
            )
        if response.status_code != 201:
            raise GitHubError(f"GitHub comment failed with HTTP {response.status_code}: {_safe_message(response)}")


def _safe_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300]
    return str(payload.get("message", "unknown error"))[:300]


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
