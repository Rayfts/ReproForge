from __future__ import annotations

from collections.abc import Callable

from reproforge.harnesses.base import CapabilityReport, HarnessInvocation, HarnessRunRequest, IntegrationMode
from reproforge.harnesses.invocations import (
    aider_invocation,
    claude_invocation,
    cline_invocation,
    codex_invocation,
    continue_invocation,
    gemini_invocation,
    goose_invocation,
    opencode_invocation,
    pi_invocation,
)

Builder = Callable[[HarnessRunRequest], HarnessInvocation]
AdapterSpec = tuple[CapabilityReport, str | None, Builder | None]

CAPABILITIES: dict[str, AdapterSpec] = {
    "codex": (
        CapabilityReport(
            id="codex",
            display_name="OpenAI Codex",
            repository="openai/codex",
            integration_modes=[IntegrationMode.HEADLESS, IntegrationMode.JSON_STREAM],
            structured_output=True,
            supports_resume=True,
            supports_mcp=True,
            evidence_urls=[
                "https://github.com/openai/codex/blob/main/codex-rs/exec/src/cli.rs",
                "https://github.com/openai/codex/blob/main/codex-rs/exec/src/exec_events.rs",
            ],
        ),
        "codex",
        codex_invocation,
    ),
    "claude-code": (
        CapabilityReport(
            id="claude-code",
            display_name="Claude Code",
            repository="anthropics/claude-code",
            integration_modes=[IntegrationMode.HEADLESS, IntegrationMode.JSON_STREAM],
            structured_output=True,
            supports_resume=True,
            supports_mcp=True,
            evidence_urls=[
                "https://github.com/anthropics/claude-code",
                "https://github.com/aaif-goose/goose/blob/main/crates/goose/src/providers/claude_code.rs",
            ],
            limitations=[
                "The public repository does not expose all product source; ReproForge uses documented CLI surfaces only."
            ],
        ),
        "claude",
        claude_invocation,
    ),
    "opencode": (
        CapabilityReport(
            id="opencode",
            display_name="OpenCode",
            repository="anomalyco/opencode",
            integration_modes=[IntegrationMode.CLI, IntegrationMode.JSON_STREAM],
            structured_output=True,
            supports_resume=True,
            supports_mcp=True,
            evidence_urls=["https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/cli/cmd/run.ts"],
        ),
        "opencode",
        opencode_invocation,
    ),
    "pi": (
        CapabilityReport(
            id="pi",
            display_name="Pi",
            repository="earendil-works/pi",
            integration_modes=[IntegrationMode.CLI, IntegrationMode.JSON_STREAM, IntegrationMode.RPC],
            structured_output=True,
            supports_resume=True,
            evidence_urls=[
                "https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/usage.md",
                "https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/index.md",
            ],
        ),
        "pi",
        pi_invocation,
    ),
    "gemini-cli": (
        CapabilityReport(
            id="gemini-cli",
            display_name="Gemini CLI",
            repository="google-gemini/gemini-cli",
            integration_modes=[IntegrationMode.HEADLESS, IntegrationMode.JSON_STREAM],
            structured_output=True,
            supports_mcp=True,
            evidence_urls=["https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md"],
        ),
        "gemini",
        gemini_invocation,
    ),
    "aider": (
        CapabilityReport(
            id="aider",
            display_name="Aider",
            repository="Aider-AI/aider",
            integration_modes=[IntegrationMode.HEADLESS],
            structured_output=False,
            evidence_urls=[
                "https://github.com/Aider-AI/aider/blob/main/aider/website/docs/scripting.md",
                "https://github.com/Aider-AI/aider/blob/main/aider/args.py",
            ],
            limitations=[
                "The verified one-shot CLI path is text-oriented; ReproForge captures stdout/stderr and filesystem evidence."
            ],
        ),
        "aider",
        aider_invocation,
    ),
    "goose": (
        CapabilityReport(
            id="goose",
            display_name="Goose",
            repository="aaif-goose/goose",
            integration_modes=[IntegrationMode.HEADLESS, IntegrationMode.JSON_STREAM],
            structured_output=True,
            supports_resume=True,
            supports_mcp=True,
            evidence_urls=["https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/running-tasks.md"],
        ),
        "goose",
        goose_invocation,
    ),
    "cline": (
        CapabilityReport(
            id="cline",
            display_name="Cline",
            repository="cline/cline",
            integration_modes=[IntegrationMode.HEADLESS, IntegrationMode.JSON_STREAM],
            structured_output=True,
            supports_mcp=True,
            evidence_urls=["https://github.com/cline/cline/blob/main/apps/cli/README.md"],
        ),
        "cline",
        cline_invocation,
    ),
    "roo-code": (
        CapabilityReport(
            id="roo-code",
            display_name="Roo Code",
            repository="RooCodeInc/Roo-Code",
            integration_modes=[IntegrationMode.ARCHIVAL],
            launchable=False,
            structured_output=False,
            limitations=[
                "The official repository is archived.",
                "The official README states the Roo Code extension was shut down on May 15, 2026.",
                "ReproForge does not invent a current CLI or headless mode for Roo Code.",
            ],
            evidence_urls=["https://github.com/RooCodeInc/Roo-Code/blob/main/README.md"],
        ),
        None,
        None,
    ),
    "continue": (
        CapabilityReport(
            id="continue",
            display_name="Continue",
            repository="continuedev/continue",
            integration_modes=[IntegrationMode.HEADLESS],
            structured_output=True,
            supports_mcp=True,
            evidence_urls=[
                "https://github.com/continuedev/continue/blob/main/docs/cli/headless-mode.mdx",
                "https://github.com/continuedev/continue/blob/main/extensions/cli/README.md",
            ],
        ),
        "cn",
        continue_invocation,
    ),
}
