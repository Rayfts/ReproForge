# Support

ReproForge is a pre-1.0 open-source project. Community support is provided on a best-effort basis; there is no guaranteed response time or commercial SLA.

## Before opening an issue

Check the README and relevant documents under `docs/`, then run:

```bash
reproforge doctor
reproforge harnesses
```

For harness-specific problems, include the harness name/version and the output of `reproforge capabilities <harness>` when safe to share.

## Bugs

Use the bug-report issue form and include a minimal reproduction, ReproForge version/commit, OS, Python and Docker versions, relevant configuration, and sanitized logs. Never attach credentials or private source code unless you intentionally want it public.

## Feature requests

Use the feature-request form. Describe the maintainer problem, the expected workflow, and why the change belongs in ReproForge rather than a specific coding-agent harness.

## Security

Do not report vulnerabilities in a normal issue. Follow `SECURITY.md`.

## Questions

A normal GitHub issue is acceptable for focused usage questions that are not answered by the documentation. Please keep one problem per issue so answers remain searchable.