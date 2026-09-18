from pathlib import Path

import pytest

from reproforge.harnesses import capability_catalog, create_adapter, harness_ids
from reproforge.harnesses.base import HarnessRunRequest


def _request() -> HarnessRunRequest:
    return HarnessRunRequest(prompt="reproduce it", cwd=Path("/workspace"))


def test_catalog_has_exact_initial_harness_set() -> None:
    assert set(harness_ids()) == {
        "codex",
        "claude-code",
        "opencode",
        "pi",
        "gemini-cli",
        "aider",
        "goose",
        "cline",
        "roo-code",
        "continue",
    }
    assert len(capability_catalog()) == 10


def test_verified_cli_invocations() -> None:
    codex = create_adapter("codex").build_invocation(_request())
    pi = create_adapter("pi").build_invocation(_request())
    gemini = create_adapter("gemini-cli").build_invocation(_request())
    goose = create_adapter("goose").build_invocation(_request())
    cline = create_adapter("cline").build_invocation(_request())
    continue_cli = create_adapter("continue").build_invocation(_request())

    assert codex.argv[:3] == ["codex", "exec", "--json"]
    assert "--ephemeral" in codex.argv
    assert pi.argv[:3] == ["pi", "--mode", "json"]
    assert "-p" in pi.argv
    assert gemini.argv[-2:] == ["--output-format", "stream-json"]
    assert goose.argv[:4] == ["goose", "run", "--output-format", "stream-json"]
    assert cline.argv[:2] == ["cline", "--json"]
    assert continue_cli.argv[:2] == ["cn", "-p"]


def test_pi_capability_points_to_current_upstream() -> None:
    pi = next(item for item in capability_catalog() if item.id == "pi")
    assert pi.repository == "mitsuhiko/pi-mono"
    assert all("earendil-works/pi" not in url for url in pi.evidence_urls)


def test_roo_code_is_archival_not_fake_cli() -> None:
    adapter = create_adapter("roo-code")
    with pytest.raises(RuntimeError, match="no current supported headless launcher"):
        adapter.build_invocation(_request())
