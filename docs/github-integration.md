# GitHub integration

ReproForge can ingest GitHub issue URLs, clone private GitHub repositories using host-only Git authentication, archive evidence, and optionally post a concise evidence comment. GitHub credentials stay in the control plane and are never part of the default sandbox environment.

## Included triggers

`.github/workflows/reproforge-dispatch.yml` supports:

- manual `workflow_dispatch` runs;
- an issue labeled `repro`;
- a maintainer/collaborator issue comment equal to `/repro` or beginning with `/repro `.

Pull-request comments are excluded. Comment-triggered runs require the comment author's GitHub association to be `OWNER`, `MEMBER`, or `COLLABORATOR`, which prevents arbitrary public commenters from consuming privileged Actions capacity.

The repository ships `.reproforge.yml` as a working self-reproduction example. Other projects should provide their own runtime image/setup/test configuration and can adapt the workflow when ReproForge is consumed as an external action or installed package.

## Result comment shape

`reproforge issue <url> --post-comment` posts concise evidence only:

- status and confidence;
- failing command when available;
- environment image/revision;
- reproduction rate and determinism;
- observed signal;
- proposed regression test;
- up to three caveats;
- run ID for the archived evidence bundle.

Verbose agent narration is intentionally excluded.

## Permissions

Issue ingestion and private cloning use control-plane credentials. Posting evidence requires `issues: write`; source checkout requires `contents: read`. The included workflow grants only those permissions. Generated patches remain evidence artifacts and are never pushed automatically.

## Private repository cloning

For `https://github.com/...` clones, ReproForge can use the resolved `GITHUB_TOKEN` or `GH_TOKEN` only in the host Git process through ephemeral Git configuration environment variables. The token is not embedded in the clone URL, written to the repository, or mounted into Docker.

## Sandbox secret boundary

Repository configuration cannot grant itself access to host environment variables. Names requested by `security.allowed_environment` and `security.allowed_secrets` must also be explicitly granted by the operator through `REPROFORGE_ENV_GRANTS` and `REPROFORGE_SECRET_GRANTS`.

`GITHUB_TOKEN` and `GH_TOKEN` are always blocked from sandbox injection, even if requested and operator-granted. Never weaken this boundary merely to make repository setup easier.

## GitHub App direction

The workflow is the initial automation surface. A future GitHub App can use the same CLI/report contracts while replacing workflow credentials and dispatch logic with installation tokens, queues, and hosted sandbox workers. The App should preserve the same least-privilege and no-auto-push rules.
