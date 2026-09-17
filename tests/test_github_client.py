import pytest

from reproforge.github.client import GitHubClient


def test_parse_issue_url() -> None:
    ref = GitHubClient.parse_issue_url("https://github.com/org/project/issues/123")
    assert ref.owner == "org"
    assert ref.repo == "project"
    assert ref.number == 123


def test_parse_issue_url_rejects_non_issue_url() -> None:
    with pytest.raises(ValueError):
        GitHubClient.parse_issue_url("https://github.com/org/project/pull/123")
