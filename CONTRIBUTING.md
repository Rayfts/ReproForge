# Contributing to ReproForge

ReproForge executes untrusted software, so correctness and containment matter more than convenience.

## Development setup

Python 3.12+ is supported. `uv` is the recommended contributor workflow:

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -m "not integration"
uv build
```

Run Docker integration tests separately:

```bash
uv run pytest -m integration
```

## Design rules

1. Never add a host-execution fallback for target repository code.
2. Never pass the ambient environment into a sandbox.
3. Agent statements are not reproduction evidence. Add or improve a deterministic oracle instead.
4. Do not invent third-party CLI flags or event fields. Link adapter changes to upstream source or official documentation.
5. Keep `report.json` backward-compatible within its schema version. A breaking change requires a new version and migration notes.
6. Generated patches are artifacts. Do not push them automatically.
7. Add tests for security-boundary changes and new detection rules.

## Harness changes

For a harness adapter, include the upstream repository, integration mode, verified invocation, event/output model, authentication constraints, supported-version policy, and known limitations. See `docs/harness-adapter-guide.md`.

## Fixture repositories

Fixture projects are intentionally broken. Keep each failure deterministic and small. Avoid real credentials, external production services, or destructive behavior.

## Pull requests

Keep changes reviewable and describe the evidence used to validate behavior. Security-sensitive changes should explain how the host/sandbox trust boundary is preserved.
