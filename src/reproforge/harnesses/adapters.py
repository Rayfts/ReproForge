from __future__ import annotations

from collections.abc import Callable

from reproforge.harnesses.base import (
    ArchivalHarnessAdapter,
    CapabilityReport,
    CliHarnessAdapter,
    HarnessAdapter,
    HarnessInvocation,
    HarnessRunRequest,
    HarnessRuntime,
    IntegrationMode,
)

Builder = Callable[[HarnessRunRequest], HarnessInvocation]


def _invocation(
    request: HarnessRunRequest,
    argv: list[str],
    *,
    structured: bool,
    stdin_text: str | None = None,
) -> HarnessInvocation:
    return HarnessInvocation(
        argv=argv,
        cwd=request.cwd,
        env=request.env,
        stdin_text=stdin_text,
        structured_output=structured,
    )


def _codex(request: HarnessRunRequest) -> HarnessInvocation:
    argv = ["codex", "exec", "--json", "--ephemeral"]
    if request.model:
        argv.extend(["--model", request.model])
    argv.append(request.prompt)
    return _invocation(request, argv, structured=True)


def _claude(request: HarnessRunRequest) -> HarnessInvocation:
    argv = [
        "claude",
        "-p",
        request.prompt,
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    if request.model:
        argv.extend(["--model", request.model])
    return _invocation(request, argv, structured=True)


def _opencode(request: HarnessRunRequest) -> HarnessInvocation:
    argv = ["opencode", "run", "--format", "json"]
    if request.model:
        argv.extend(["--model", request.model])
    if request.session_id:
        argv.extend(["--session", request.session_id])
    argv.append(request.prompt)
    return _invocation(request, argv, structured=True)


def _pi(request: HarnessRunRequest) -> HarnessInvocation:
    argv = ["pi", "--mode", "json", "-p"]
    if request.model:
        argv.extend(["--model", request.model])
    argv.append(request.prompt)
    return _invocation(request, argv, structured=True)


def _gemini(request: HarnessRunRequest) -> HarnessInvocation:
    argv = ["gemini", "-p", request.prompt, "--output-format", "stream-json"]
    if request.model:
        argv.extend(["--model", request.model])
    return _invocation(request, argv, structured=True)


def _aider(request: HarnessRunRequest) -> HarnessInvocation:
    argv = [
        "aider",
        "--message",
        request.prompt,
        "--yes",
        "--no-auto-commits",
    ]
    if request.model:
        argv.extend(["--model", request.model])
    return _invocation(request, argv, structured=False)


def _goose(request: HarnessRunRequest) -> HarnessInvocation:
    argv = [
        "goose",
        "run",
        "--output-format",
        "stream-json",
        "--no-session",
        "-t",
        request.prompt,
    ]
    if request.model:
        argv.extend(["--model", request.model])
    return _invocation(request, argv, structured=True)


def _cline(request: HarnessRunRequest) -> HarnessInvocation:
    argv = ["cline", "--json"]
    if request.model:
        argv.extend(["-m", request.model])
    argv.append(request.prompt)
    return _invocation(request, argv, structured=True)


def _continue(request: HarnessRunRequest) -> HarnessInvocation:
    # The verified headless surface is `cn -p ... --format json`.
    # Model selection stays in Continue configuration until a stable CLI flag
    # is verified from upstream source.
    return _invocation(
        request,
        ["cn", "-p", request.prompt, "--format", "json"],
        structured=True,
    )


_CAPABILITIES: dict[str, tuple[CapabilityReport, str | None, Builder | None]] = {
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
        _codex,
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
        _claude,
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
        _opencode,
    ),
    "pi": (
        CapabilityReport(
            id="pi",
            display_name="Pi",
            repository="earendil-works/pi",
            integration_modes=[
                IntegrationMode.CLI,
                IntegrationMode.JSON_STREAM,
                IntegrationMode.RPC,
            ],
            structured_output=True,
            supports_resume=True,
            evidence_urls=[
                "https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/usage.md",
                "https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/index.md",
            ],
        ),
        "pi",
        _pi,
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
        _gemini,
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
        _aider,
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
        _goose,
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
        _cline,
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
        _continue,
    ),
}


def harness_ids() -> tuple[str, ...]:
    return tuple(_CAPABILITIES)


def create_adapter(
    harness_id: str,
    *,
    runtime: HarnessRuntime | None = None,
) -> HarnessAdapter:
    try:
        capability, executable, builder = _CAPABILITIES[harness_id]
    except KeyError as exc:
        known = ", ".join(harness_ids())
        raise ValueError(f"unknown harness {harness_id!r}; expected one of: {known}") from exc

    if executable is None or builder is None:
        return ArchivalHarnessAdapter(capability)

    return CliHarnessAdapter(
        capability=capability,
        executable=executable,
        invocation_builder=builder,
        runtime=runtime,
    )


def capability_catalog() -> list[CapabilityReport]:
    return [entry[0].model_copy(deep=True) for entry in _CAPABILITIES.values()]
