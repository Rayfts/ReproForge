# Sandbox design

Docker is ReproForge's initial execution backend.

## Defaults

A run uses:

- `--cap-drop ALL`;
- `--security-opt no-new-privileges`;
- a read-only container root;
- writable bind mount of only the selected workspace at `/workspace`;
- tmpfs `/tmp` and `HOME=/tmp/reproforge-home`;
- no Docker socket mount;
- no host home mount;
- no ambient environment inheritance;
- `--network none` unless explicitly changed;
- CPU, memory, PID, and per-command time limits.

The control process refuses to execute repository commands directly on the host if Docker is unavailable.

## Persistent run container

Setup, baseline, and independent attempts share one disposable `DockerSession`. Language caches and virtual environments are placed under `.reproforge/runtime` in the workspace because the container root is read-only. Runtime caches are excluded from exported evidence.

A separate disposable harness container can share the workspace. This lets the agent create a failing test or reproduction artifact while keeping its own executable/provider stack independent from the project runtime image.

## Images

ReproForge does not attempt to construct a universal runtime image. Set `sandbox.image` explicitly or in `.reproforge.yml`. For reproducible production use, prefer image digests over floating tags.

When using an agent, set `harness.image` if the project image does not contain the harness binary.

## Network policy

Docker's `none` and `bridge` modes are implemented. Domain allowlists are **not yet enforced** by the Docker backend. `security.allowed_network_domains` exists for forward-compatible configuration and must not be treated as a firewall rule today.

## Secret injection

Secrets are opt-in. An allowed secret is available to every process in the container receiving it; use only credentials whose exposure to the target repository is acceptable.

## Future backends

The `SandboxBackend` contract is intended to support Podman, Firecracker/microVMs, and cloud sandboxes. A backend is acceptable only if it preserves or strengthens the documented host isolation properties.
