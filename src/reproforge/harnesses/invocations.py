from __future__ import annotations

from reproforge.harnesses.base import HarnessInvocation, HarnessRunRequest


def _invocation(
    request: HarnessRunRequest,
    argv: list[str],
    *,
    structured: bool,
) -> HarnessInvocation:
    return HarnessInvocation(
        argv=argv,
        cwd=request.cwd,
        env=request.env,
        structured_output=structured,
    )


def codex_invocation(request: HarnessRunRequest) -> HarnessInvocation:
    argv = ["codex", "exec", "--json", "--ephemeral"]
    if request.model:
        argv.extend(["--model", request.model])
    argv.append(request.prompt)
    return _invocation(request, argv, structured=True)


def claude_invocation(request: HarnessRunRequest) -> HarnessInvocation:
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


def opencode_invocation(request: HarnessRunRequest) -> HarnessInvocation:
    argv = ["opencode", "run", "--format", "json"]
    if request.model:
        argv.extend(["--model", request.model])
    if request.session_id:
        argv.extend(["--session", request.session_id])
    argv.append(request.prompt)
    return _invocation(request, argv, structured=True)


def pi_invocation(request: HarnessRunRequest) -> HarnessInvocation:
    argv = ["pi", "--mode", "json", "-p"]
    if request.model:
        argv.extend(["--model", request.model])
    argv.append(request.prompt)
    return _invocation(request, argv, structured=True)


def gemini_invocation(request: HarnessRunRequest) -> HarnessInvocation:
    argv = ["gemini", "-p", request.prompt, "--output-format", "stream-json"]
    if request.model:
        argv.extend(["--model", request.model])
    return _invocation(request, argv, structured=True)


def aider_invocation(request: HarnessRunRequest) -> HarnessInvocation:
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


def goose_invocation(request: HarnessRunRequest) -> HarnessInvocation:
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


def cline_invocation(request: HarnessRunRequest) -> HarnessInvocation:
    argv = ["cline", "--json"]
    if request.model:
        argv.extend(["-m", request.model])
    argv.append(request.prompt)
    return _invocation(request, argv, structured=True)


def continue_invocation(request: HarnessRunRequest) -> HarnessInvocation:
    # Verified headless surface: `cn -p ... --format json`.
    # Model selection remains in Continue config until an upstream CLI flag is verified.
    return _invocation(
        request,
        ["cn", "-p", request.prompt, "--format", "json"],
        structured=True,
    )
