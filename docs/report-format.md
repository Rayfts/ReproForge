# Report format

`report.json` is the machine-readable source of truth for a run. Its current schema version is `1.0`.

## Core fields

- `schema_version`: stable format discriminator.
- `run_id`: unique ReproForge run identifier.
- `status`: categorical outcome.
- `confidence`: numeric value in `[0, 1]`, separate from status.
- `request`: local/GitHub issue input and selected harness/revision.
- `environment`: sandbox backend, image, limits, revision, network policy, and detected project profile.
- `setup_commands`: observed dependency/setup process results.
- `baseline_commands`: observed pre-investigation build/check results.
- `attempts`: repeated reproduction commands and observed signals.
- `primary_signal`: representative observed failure, if present.
- `reproduction_rate`: fraction of attempts that produced a failure signal.
- `deterministic`: whether every attempt produced the same failure fingerprint.
- `harness_interpretation`: agent interpretation, explicitly separate from observed evidence.
- `generated_regression_test`: proposed test description/path.
- `minimized_reproduction`: reduced command sequence when proven to preserve the same failure fingerprint.
- `caveats`: limitations encountered during the run.
- `artifacts`: paths to relevant generated artifacts.

## Status values

`reproduced`, `probably-reproduced`, `not-reproduced`, `flaky`, `insufficient-information`, `setup-failure`, `infrastructure-failure`, `invalid-report`, and `inconclusive`.

Status and confidence intentionally remain separate. A run can have a clear category while still carrying limited confidence about whether the observed failure semantically matches the human report.

## JSONL files

`commands.jsonl` records setup, baseline, and attempt command results with phase metadata. `attempts.jsonl` records one complete attempt per line.

## Redaction

Configured secret values and common credential-shaped strings are redacted before report files are written. Redaction is defense in depth; it is not a substitute for avoiding unnecessary secret injection.

## Compatibility

Additive optional fields may be introduced within `1.0`. Removing/renaming fields or changing their meaning requires a new schema version and migration documentation.
