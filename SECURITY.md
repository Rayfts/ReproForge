# Security Policy

ReproForge intentionally executes untrusted repositories and should be treated as security-sensitive infrastructure.

## Reporting a vulnerability

Please do not publish exploit details, credentials, sandbox escapes, or secret-exfiltration techniques in a public issue.

If GitHub private vulnerability reporting is enabled for the repository, use **Security → Report a vulnerability**. Otherwise, open a minimal public issue that contains no sensitive details and asks the maintainer for a private reporting channel.

Useful reports include the affected commit/version, operating system, Docker version, minimal reproduction, expected impact, and whether the issue can escape the container, access unintended host data, or expose an explicitly injected secret.

## Security invariants

ReproForge must not silently:

- execute target repository commands directly on the host;
- mount the Docker socket, SSH keys, cloud credentials, or the user's home directory;
- inherit ambient environment variables;
- inject GitHub/model/provider credentials without explicit operator approval;
- enable network access merely because setup failed without it;
- automatically push agent-generated changes.

The workspace is intentionally writable because reproduction may create tests, fixtures, or patches. Treat every resulting file as untrusted.

## Secret injection

Explicit secret injection is an escape hatch, not a safety guarantee. Code inside the sandbox can read injected values and may exfiltrate them when network access is permitted. Prefer short-lived, narrowly scoped credentials and avoid secrets for arbitrary third-party issue reproductions.

See `docs/threat-model.md` and `docs/sandbox.md` for the detailed trust model.