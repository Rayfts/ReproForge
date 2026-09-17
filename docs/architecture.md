# Architecture

ReproForge separates **investigation** from **validation**.

```text
issue/local input
      |
      v
control plane ----> repository inspection + project detection
      |                         |
      |                         v
      |                  Docker environment
      |                  setup -> baseline
      |                         |
      v                         v
harness adapter --------> investigation workspace
      |                         |
      |                         v
      |                 exact reproduction plan
      |                         |
      +-------------------------+
                                v
                     deterministic validator
                     repeat -> fingerprint
                                |
                                v
                       minimizer + reports
```

## Control plane

The Python control plane fetches GitHub issue metadata, clones repositories, inspects manifests/instructions/workflows, selects explicit environment variables, starts Docker containers, records results, and writes reports. GitHub API credentials remain on this side unless a user explicitly allowlists a secret for sandbox injection.

## Repository analysis

`reproforge.detectors` recognizes Python, Node.js/TypeScript, React, Rust, Go, common package managers, lock files, test commands, build commands, and Docker Compose service declarations. `.reproforge.yml` can override detected setup/build/test commands.

## Sandbox

A `SandboxBackend` abstraction keeps the execution API independent of Docker. Docker is the initial backend. `DockerSession` maintains one disposable container across setup, baseline, and attempts so installed dependencies persist without exposing the host filesystem beyond the workspace.

Future Podman, Firecracker, and cloud backends should implement the same execution contract without weakening the security invariants.

## Harness layer

Harness adapters expose capability metadata and build only verified invocations. Execution is delegated to `HarnessRuntime`; the current runtime uses an isolated Docker session. Structured upstream events are normalized to ReproForge event kinds but the original raw line is retained.

A harness can suggest exact commands and create a regression test. It cannot set the final reproduction status.

## Validation

`validation.oracles` derives signals from process facts: timeout, exit code, panic, assertion failure, exception, compiler/runtime error, snapshot/HTTP mismatch, or generic test failure. Repeated attempts are fingerprinted after normalizing unstable addresses/timing/stack-frame locations.

`reproduced` requires the observed failure to occur on every requested attempt with the same fingerprint. Partial rates become `probably-reproduced` or `flaky` according to configuration.

## Minimization

The first implemented reducer is command-sequence `ddmin`. It removes command subsets only when rerunning the candidate preserves the same observed failure fingerprint. Input/file/request reducers can use the same predicate-oriented design later.

## Persistence

The working copy receives the latest `.reproforge/` evidence bundle. The CLI archives each completed run under `REPROFORGE_HOME` and indexes it in SQLite for `inspect`, `resume`, and `export`.
