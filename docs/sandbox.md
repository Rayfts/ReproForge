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

## Workspace mount policy

Before inspecting or mounting a local workspace, ReproForge resolves the path and checks it against a non-removable sensitive-path baseline: `~/.ssh`, `~/.aws`, `~/.config/gh`, and `/var/run/docker.sock`. A workspace is rejected if it equals, contains, or sits inside one of those paths. Repository configuration can add entries through `security.forbidden_filesystem_paths`, but it cannot remove the baseline protections.

A blocked run does not create `.reproforge` inside the rejected workspace. Its minimal infrastructure-failure evidence is written only to the control-plane run archive under `REPROFORGE_HOME`.

## Persistent run container

Setup, baseline, and independent attempts share one disposable `DockerSession`. Language caches and virtual environments are placed under `.reproforge/runtime` in the workspace because the container root is read-only. Runtime caches are excluded from exported evidence.

A separate disposable harness container can share the workspace. This lets the agent create a failing test or reproduction artifact while keeping its own executable/provider stack independent from the project runtime image.

If a command times out, ReproForge stops and restarts that disposable run container before continuing so a killed host-side `docker exec` client cannot leave an unknown process running in the sandbox.

## Images

ReproForge does not attempt to construct a universal runtime image. Set `sandbox.image` explicitly or in `.reproforge.yml`. For reproducible production use, prefer image digests over floating tags.

When using an agent, set `harness.image` if the project image does not contain the harness binary.

## Network policy

Docker's `none` and `bridge` modes are implemented. Domain allowlists are **not yet enforceable** by the Docker backend. If `security.allowed_network_domains` is non-empty, ReproForge fails closed before repository code executes instead of silently degrading the request to unrestricted bridge networking.

Use `network: none` for the safest default. `network: bridge` permits the container's normal Docker bridge connectivity and should be enabled only when repository setup or reproduction genuinely requires network access.

## Secret injection

Repository configuration may request host environment names, but it does not authorize them. The operator must separately grant ordinary environment names through `REPROFORGE_ENV_GRANTS` and secret names through `REPROFORGE_SECRET_GRANTS`. `GITHUB_TOKEN` and `GH_TOKEN` are reserved control-plane credentials and are never injected into a sandbox through either grant channel.

An injected non-control-plane secret is available to every process in the receiving container. Use only credentials whose exposure to the target repository is acceptable.

## Future backends

The `SandboxBackend` contract is intended to support Podman, Firecracker/microVMs, and cloud sandboxes. A backend is acceptable only if it preserves or strengthens the documented host isolation properties.
