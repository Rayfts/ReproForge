# Contributing to ReproForge

Thanks for helping improve ReproForge. Contributions are welcome across the reproduction engine, sandboxing, project detection, harness adapters, reports, fixtures, documentation, and GitHub integration.

ReproForge executes untrusted software, so correctness and containment matter more than convenience.

## Development setup

Python 3.12+ is supported. `uv` is the recommended workflow:

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

## Project rules

1. Never add a host-execution fallback for target repository code.
2. Never pass the ambient host environment into a sandbox.
3. Agent statements are analysis, not reproduction evidence. Deterministic validation remains the oracle.
4. Do not invent third-party CLI flags, event fields, or capabilities. Adapter changes must be backed by upstream source or official documentation.
5. Keep versioned report formats backward-compatible within a schema version.
6. Generated fixes and tests are artifacts; do not push them automatically.
7. Security-boundary changes require focused tests.
8. Keep Python source and test files at 300 physical lines or fewer; split by responsibility rather than compressing logic.

## Harness adapters

When adding or changing an adapter, document the upstream repository, invocation mode, output/event format, authentication assumptions, supported-version policy, and known limitations. Update the capability documentation and contract tests in the same pull request.

## Fixture repositories

Fixtures are intentionally broken. Keep failures deterministic, small, offline-friendly where practical, and free of real credentials or destructive behavior.

## Pull requests

Keep PRs focused. Explain what changed, why it is safe, how it was tested, and any compatibility or security implications. If behavior affects evidence classification, include a fixture or regression test that demonstrates the expected result.

By contributing, you agree to follow the repository's `CODE_OF_CONDUCT.md` and Apache-2.0 license terms.