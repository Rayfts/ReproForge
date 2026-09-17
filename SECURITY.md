# Security policy

ReproForge intentionally executes untrusted repositories and should be treated as security-sensitive infrastructure.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub Security Advisories for `Rayfts/ReproForge` when available. Do not open a public issue containing an exploit, credential, or bypass for the sandbox boundary.

Include the affected version/commit, operating system, Docker version, minimal reproduction, impact, and whether the issue can escape the container, read unintended host data, or exfiltrate an explicitly injected secret.

## Security invariants

ReproForge must not silently:

- execute target repository commands directly on the host;
- mount `/var/run/docker.sock`, host SSH keys, cloud credentials, or the user's home directory;
- inherit ambient environment variables;
- inject `GITHUB_TOKEN`, `GH_TOKEN`, or provider credentials unless the user explicitly allowlists them;
- enable network access merely because setup failed without it;
- automatically push an agent-generated patch.

The workspace itself is intentionally writable and bind-mounted because reproduction may need to create tests or fixtures. Treat all resulting files as untrusted.

## Explicit secret injection

`security.allowed_secrets` is an escape hatch, not a safety guarantee. An injected secret is readable by processes in the sandbox. If network is enabled, untrusted code may be able to exfiltrate it. Prefer short-lived, narrowly scoped credentials and avoid injecting secrets into arbitrary issue reproductions.

See `docs/threat-model.md` for the detailed model.
