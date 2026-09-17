# Harness adapter guide

A harness adapter converts a verified upstream integration surface into ReproForge's normalized event stream. It must not decide whether a bug is reproduced.

## Contract

Conceptually every adapter supports:

```python
async def detect() -> CapabilityReport: ...
async def prepare(request: HarnessRunRequest) -> None: ...
async def run(request: HarnessRunRequest) -> AsyncIterator[HarnessEvent]: ...
async def cancel() -> None: ...
```

`build_invocation()` is also exposed by the built-in CLI adapters so exact argv can be unit-tested without launching the tool.

## Required evidence for a new adapter

Document:

1. upstream repository;
2. supported invocation/headless/import mechanism;
3. exact flags or API fields and the upstream source file/docs that define them;
4. structured output/event semantics, if any;
5. session/resume behavior;
6. MCP/plugin/hook behavior if used;
7. authentication requirements;
8. known limitations and supported-version policy.

Do not derive a production adapter solely from a blog post or a third-party wrapper when upstream source/documentation exists.

## Runtime boundary

`CliHarnessAdapter` does not spawn host processes. It requires an injected `HarnessRuntime`. The default `DockerHarnessRuntime` executes inside a disposable Docker session and normalizes each output line while retaining the raw event.

## Investigation output

The initial pipeline asks the harness to write `.reproforge/harness-plan.json` with exact reproduction commands, a short interpretation, and a regression-test description. ReproForge independently executes those commands and derives failure status from observed process evidence.

If the plan is absent or invalid, ReproForge records a caveat and falls back to repository-detected test commands rather than treating agent prose as evidence.
