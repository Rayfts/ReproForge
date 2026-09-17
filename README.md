# ReproForge

ReproForge turns software bug reports into **reproducible evidence**.

Instead of asking an agent whether a bug is real, ReproForge creates an isolated workspace, establishes a baseline, lets a supported coding-agent harness investigate, and then independently reruns exact commands to decide whether a measurable failure occurred.

> **Status:** early public-OSS foundation. The versioned report schema, hardened Docker execution boundary, deterministic validation engine, initial 10-harness capability layer, evidence archive, and GitHub issue workflow are implemented. A full GitHub App remains a future deployment surface rather than being presented as already deployed.

## Evidence, not agent opinion

A run can capture:

- the exact repository revision and detected project stack;
- setup, build, baseline, and reproduction commands with exit codes and timing;
- per-command stdout/stderr logs and normalized failure fingerprints;
- repeated-attempt reproduction rate and determinism;
- harness and per-attempt filesystem changes as Git patches when Git history is available;
- a minimized command sequence when reduction preserves the same failure fingerprint;
- a proposed regression test separately from observed failure evidence;
- stable JSON plus a human-readable Markdown report.

Agent interpretation is stored separately from `observed` failure signals and is never used as the reproduction oracle.

## Install

ReproForge requires Python 3.12+ and Docker for untrusted execution.

```bash
python -m pip install -e .
```

For development with `uv`:

```bash
uv sync --extra dev
uv run reproforge --help
```

## Quick start

Create `.reproforge.yml` in the target repository. ReproForge intentionally does not guess a universal Docker image because Python, Node, Rust, Go, and mixed projects require different runtimes.

```yaml
sandbox:
  image: python:3.12-slim
  network: none
  limits:
    timeout_seconds: 600
    memory_mb: 2048
    cpus: 2
    pids: 256

reproduction_attempts: 3
```

Then run:

```bash
reproforge local .
reproforge issue https://github.com/org/project/issues/123
reproforge issue https://github.com/org/project/issues/123 --harness codex
reproforge issue https://github.com/org/project/issues/123 --post-comment
```

A completed workspace contains the evidence bundle:

```text
.reproforge/
  report.json
  report.md
  environment.json
  attempts.jsonl
  commands.jsonl
  logs/
  patches/
  artifacts/
  reproduction/
  regression-test/
```

Completed runs are also archived under `REPROFORGE_HOME` (default `~/.reproforge`) so `inspect`, `resume`, and `export` do not depend on the top-level report remaining unchanged.

## CLI

```text
reproforge issue <github-url> [--harness ID] [--revision REV] [--image IMAGE] [--post-comment]
reproforge local <path> [--harness ID] [--image IMAGE]
reproforge resume <run-id>
reproforge inspect <run-id> [--json]
reproforge export <run-id> [-o bundle.zip]
reproforge doctor
reproforge harnesses
reproforge capabilities <harness> [--detect]
```

`resume` continues from the stored workspace and prior request. It starts a new evidence run; it does not claim that every third-party harness can resume its own conversational session.

## GitHub automation

The included issue workflow supports manual dispatch, a `repro` issue label, and maintainer/collaborator `/repro` comments. It uploads the archived evidence bundle and can post the concise evidence summary back to the issue. Generated patches remain artifacts; ReproForge never pushes them automatically.

Private GitHub issue repositories can be cloned using the control-plane GitHub token. Clone authentication is scoped to the host Git process and is not written into the repository or passed to Docker.

## Harness support

ReproForge does not pretend every coding agent has the same integration surface.

| Harness | Upstream | ReproForge strategy | Structured output |
| --- | --- | --- | --- |
| OpenAI Codex | `openai/codex` | `codex exec` JSONL | Yes |
| Claude Code | `anthropics/claude-code` | headless `claude` stream JSON | Yes |
| OpenCode | `anomalyco/opencode` | `opencode run --format json` | Yes |
| Pi | `earendil-works/pi` | JSON mode; upstream also exposes RPC | Yes |
| Gemini CLI | `google-gemini/gemini-cli` | non-interactive stream JSON | Yes |
| Aider | `Aider-AI/aider` | one-shot CLI, captured stdout/stderr | No verified event stream |
| Goose | `aaif-goose/goose` | headless stream JSON | Yes |
| Cline | `cline/cline` | headless NDJSON CLI | Yes |
| Roo Code | `RooCodeInc/Roo-Code` | **archival only** | No |
| Continue | `continuedev/continue` | `cn -p ... --format json` | Yes |

The official Roo Code repository is archived and its README states that the extension was shut down on May 15, 2026. ReproForge therefore refuses to invent a current Roo Code launcher. See [the capability research](docs/harness-capabilities.md) for source evidence and limitations.

Harness binaries are expected to exist in `harness.image` (or the project sandbox image). ReproForge does not mount your host home directory into that container.

## Security model

Repositories and issue text are untrusted input. Default execution properties include:

- Docker-only execution; no fallback to host execution;
- no host Docker socket, SSH directory, cloud config, or arbitrary host filesystem mounts;
- isolated `HOME` on tmpfs;
- `--cap-drop ALL` and `no-new-privileges`;
- read-only container root by default;
- CPU, memory, PID, and command time limits;
- network disabled by default;
- no inherited host environment;
- repository-requested host values require a separate operator grant;
- `GITHUB_TOKEN` and `GH_TOKEN` are never sandbox-injectable;
- domain allowlists fail closed until a backend can actually enforce them;
- redaction of configured secret values from evidence output.

Repository configuration may request host variable names, but the operator must separately grant them with `REPROFORGE_ENV_GRANTS` or `REPROFORGE_SECRET_GRANTS` (comma-separated names). Allowing any non-control-plane secret or enabling network access is an explicit trust decision: code inside the sandbox can potentially read an injected secret and send it over permitted network access. Read [the threat model](docs/threat-model.md) before using secrets with untrusted repositories.

The repository's own `.reproforge.yml` enables Docker bridge networking because its self-reproduction setup installs development dependencies. That project-specific configuration does not change ReproForge's global `network: none` default.

## Seeded fixtures

`fixture_repos/` contains intentionally broken Python, TypeScript, Rust, Go, React, and HTTP-server projects. They exist to prove the validation engine can observe real seeded failures. They are bugs by design.

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -m "not integration"
uv build
```

Docker integration tests are separate because they execute fixture repositories in containers. CI also enforces a 300-line maximum for Python source and test files to keep modules reviewable.

## Documentation

- [Architecture](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Sandbox design](docs/sandbox.md)
- [Harness capability research](docs/harness-capabilities.md)
- [Harness adapter guide](docs/harness-adapter-guide.md)
- [Report format](docs/report-format.md)
- [GitHub integration](docs/github-integration.md)

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

Licensed under the [Apache License 2.0](LICENSE).
